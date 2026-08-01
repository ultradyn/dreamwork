# #691 — a cheap-model recap of what the main agent is doing

**Design only. Authorises no code.** You asked to review the design before
implementation, so nothing here has been built. Three open questions are in
`.dreamwork/questions.md` under `## Open`, each with a `rec`.

Everything below rests on measurements taken tonight against the live loop, not
on assumption. Where I could not measure, I say so.

**Reconciliation note (2026-08-01).** This remains the one design of record.
The unmerged `cx-691recap` branch is provenance for corrections folded below
after the reusable `dreamwork_db` and session-log seams landed; its
`recap-design.md` is not a second design and does not supersede this file.

---

## 1. What it does

Every heartbeat, about two minutes after the beat, a small Python process reads
the main dreamworker's own session transcript, projects the last few minutes of
it into a compact one-line-per-step log, and hands that to a cheap model. The
model writes two to four sentences of plain English about what the agent is
doing and how it is going. That text, and the fact of every attempt that failed
to produce one, goes into a table in the ledger store. The dashboard shows the
most recent one and cross-dissolves when it changes.

It is off unless switched on, and off means no model process is ever started.

Here is a real one, produced end-to-end by `ccc -y @glm52` from your live
session at 21:33 tonight, unedited:

> The agent is running its full pytest suite and a ledger "sweep" that checks
> for merged commits never cited in task entries, and the sweep flagged #124.
> Chasing that flag took it through two wrong sha-format hypotheses before it
> found that the entry's note claimed to cite the merge sha but never actually
> contained it. A second, larger problem then surfaced: the ledger_view
> projection is truncating #124's body, dropping over 40% of the stored text,
> and a note-add reported success without changing the parsed view, which it is
> now actively investigating.

That is accurate. I checked it against the transcript it was built from.

---

## 2. The measurements everything below rests on

| Fact | Measured value | How |
|---|---|---|
| Transcript growth | **28–35 KB/min** → ~140–170 KB per beat | timestamps over 5/15/60-min windows |
| Raw bytes in one beat window | 172 KB ≈ **43k tokens** | too big to send raw; hence the projection |
| Projected digest, one beat | **6.2 KB** (46 steps) | the projection below, run for real |
| Projected digest, 3 hours | 25 KB after elision (1,421 steps, 1,184 elided) | same |
| `ccc -y @glm52` latency | 14.8 s (70 B prompt) · **19.0 s (6 KB)** · **24.6 s (25 KB)** | three real runs |
| `ccc -y @glm52` peak memory | **238–257 MB RSS across 7 processes** | 4 Hz sampling of the process tree |
| A *steady-state* ccc lane | ~47 MB RSS / ~68 MB with swap | point sample of two live lanes |
| Compactions in the live session | 7 in 20 h ≈ **one per 145 min ≈ one per 31 beats** | `compact_boundary` timestamps |
| Host memory now | 62 GB RAM (25 GB free), swap **55 of 62 GB used**, 7 GB free | `free -m` |
| `ARG_MAX` | 2,097,152 B | `sysconf` — a 24 KiB prompt on argv is 1.2% of it |

Two facts that changed the design:

- **`ccc` will not read a prompt from stdin.** Measured: `printf … | ccc -y
  @glm52` exits 1 with `invalid request: prompt must not be empty` and zero
  bytes on stdout. The digest must go on argv.
- **The grok harness writes nothing until it exits**
  (`dogfood-orchestration.md:928-934`: *"`@pi-glm52` also writes zero bytes
  until exit"*). So there is no streaming and no partial result: a recap either
  arrives whole or does not arrive.

---

## 3. The input, and the one thing that is broken today

### 3.1 What the session log is

It is the CLI harness's own transcript: newline-delimited JSON, one record per
line, at `$CLAUDE_CONFIG_DIR/projects/<cwd-slug>/<session-uuid>.jsonl`. It is
append-only (verified under growth in `plans/session-log-view.md`) and a full
scan of the live 17 MB file takes **0.36 s**, so there is no need for an index,
a watcher, or a cursor. The recap re-scans and stops.

Actions are `tool_use` blocks in `assistant` records paired to `tool_result`
blocks in `user` records by `tool_use_id`. In the live session: 1,440 pairs,
100% matched.

### 3.2 The defect that blocks this feature as specified

**Nothing on disk currently says which transcript belongs to the main agent, and
the obvious derivation gives the wrong file.**

- `#665` built the seam for exactly this — the main agent records
  `{client, session_id, is_subagent, recorded_at}` into `status.json` under
  `agent_session` at orient (`initialization.md` step 7, `client_env.py:150`).
  **The live `.dreamwork/status.json` has no `agent_session` key.** The seam
  exists and is empty.
- Deriving the path from the target directory instead gives
  `…/projects/-home-xertrov--llm-general-skills-ud-dreamwork/`, whose newest
  file was last written **2026-07-29 14:31** — two days stale.
- The live transcript is under the slug
  `…-ud-dreamwork--worktrees-lane-clientextract`, because the session carries
  376 `relocated` records pointing at that worktree. So the directory follows a
  cwd the loop does not control and can change mid-session.

This is the `#136` shape waiting to happen: a recap built from the two-day-old
file would be fluent, confident, and about work that finished on Wednesday.

**What the design does about it.** Read the recorded main-agent session id and
pass it to the existing `session_source.resolve` seam. Accept only its `live`
result; preserve `absent`, `mismatch`, `missing`, and `stale` as distinct
`no_source` attempt details and start no model process. There is no fallback.
A "newest jsonl anywhere" or cwd-derived path is exactly the
confident-wrong-answer this loop keeps filing bugs about, and either would pick
the wrong transcript on the measured state above.

**This is worth a task of its own** — `agent_session` being unpopulated is a
`#665` regression that also silently disables the session-log view (`#613`). I
have not filed it; naming it for the coordinator per the brief.

### 3.3 What the digest contains

The projector consumes the existing `session_log` service/scanner for stable
ordering, record classification, tool-use/result pairing, diagnostics,
compaction nodes, and its event cursor. It does not add a second JSONL parser.
Advance the cursor only after a terminal `ok` or judged `unchanged` attempt;
runner failure leaves the missed actions in the next window.

One line per step, newest-relevant detail kept, bodies never:

```
21:31:04   Bash: python3 -m pytest -q test_ledger.py
21:31:44     -> 2,648 B
21:31:52 says: The sweep flagged #124 — the note claims a sha it does not carry.
```

Turn text (300 chars), tool name plus its command/path/pattern (180 chars),
result size and an `ERROR` flag, and assistant text (300 chars). Thinking blocks
are counted, not quoted. This is **0.8–1.3% of the raw bytes** and it is the
whole reason the feature is affordable.

Deliberately excluded: tool result *bodies*. The harness already offloads large
results to `<session>/tool-results/*.txt` and leaves a preview inline, so the
digest gets the truncation for free — but even the previews are the bulk of the
file, and "what came back" is almost never what a status line needs. What the
agent *did* is.

The window is **since the last successful recap**, not "the last 4.75 minutes".
If a run fails or is skipped, the next one covers the gap. Actions never fall
through a hole.

---

## 4. The compaction boundary

You compact roughly every 145 minutes. The trap is real and it is worth being
precise about why it does *not* bite here.

**The transcript is not truncated at a compaction.** Measured: the live file
holds all 7 boundaries and every pre-compaction record, continuing unbroken to
line 8,661. Only the *model's context* is compacted. So a digest built from
`tool_use` records is reading actions on both sides of a boundary — it is never
reading a summary of actions.

The way it *could* go wrong is a digest that slurps lines by count or byte
offset: each boundary is followed by a `user` record with
`isCompactSummary: true` carrying a **15–24 KB prose blob**. Straddle a boundary
naively and that blob is 80% of your prompt, and it *is* a summary of actions
wearing an action's clothes.

**The rule:** the projector drops `isCompactSummary` records entirely and
replaces the `compact_boundary` record with a marked note:

```
[08:43:43 COMPACTION (auto): the agent's context was summarised,
 347801 -> 30898 tokens. Steps below are read from the log, not from
 that summary.]
```

Verified working in the 180-minute probe, which crossed two boundaries and
marked both. The detection is a one-field test (`subtype == "compact_boundary"`,
`isCompactSummary`), so it is cheap and it is not heuristic.

Keeping the marker rather than silently dropping the boundary is deliberate:
"the agent just compacted" is *useful* to see on a dashboard, and it explains a
recap that suddenly reads as if the agent is re-orienting — because it is.

---

## 5. The cap and the elision

**Cap: 24 KiB of assembled prompt, in bytes of UTF-8.**

Bytes, because it is the only unit the wrapper can measure exactly without a
tokenizer, and cost is roughly linear in it. Not lines — a line here is 20 B or
400 B.

24 KiB is derived, not picked: one beat's digest measured **6.2 KB**, so the cap
is about **4× a normal beat**, which means elision only begins after roughly
four consecutive missed recaps — about twenty minutes of unrecapped work. Under
normal operation the cap never engages. It is a rail, not the road.

*(One thing my probe got wrong and the implementation must not: the cap belongs
to the assembled prompt, so the instruction preamble (~1 KB) and the elision
marker have to be subtracted from the budget before the body is filled. My probe
capped the body and came out at 25,152 B against a 24,576 B cap.)*

**Elision keeps the head and the tail and marks the middle**, as you specified.
Split **1/3 head, 2/3 tail**: the head carries what the agent set out to do —
the turn that opened the window, the task it grabbed — and the tail is "current
actions", which is what you asked for. Whole steps are cut, never half a line.

The marker is one line and it names what was lost:

```
[… 1184 of 1421 steps elided here, 08:47:26–11:17:53, 125 KiB.
  This recap did not see them. …]
```

Count, total, time span, volume, and an explicit statement of ignorance. This
matters more than it looks: with those numbers the model can honestly say *"and
roughly 1,200 further steps over two and a half hours"*; without them it will
either invent the middle or pretend the window was small. In the 180-minute
probe it did neither — it described the head, described the tail, and left the
middle alone.

---

## 6. Where in the DB

**`.dreamwork/ledger.sqlite3`, a new `recap` table.**

The brief asked whether `ledger.sqlite3` being gitignored matters. It does not,
because it does not discriminate: **both stores are gitignored** (`.gitignore`
lines 16–26). And for this datum travelling would be wrong anyway — a recap of
what *this machine's* agent did is machine-local by nature, the same C1 trust
boundary as everything else in that file.

What decides it is contract and mechanism:

- **`user-events.sqlite3` is out of contract.** Its design says every row is a
  receipt for a user action — *"`submissions.log`, `watch-events.log`, Markdown,
  browser history, and dashboard indexes remain shadows, projections, or wake
  signals. None is receipt authority"* (`plans/user-event-journal.md:19-20`). A
  machine-written recap has no client action id, no request digest, no payload
  bytes and no human intent to witness. It is precisely a projection. That store
  also has **no migration ladder** (it refuses to open on any version delta) and
  an explicit module-ownership fence.
- **`ledger.sqlite3` already hosts exactly this shape, but now has an ordered
  migration contract.** The current store is schema v3. Add
  `dreamwork_db/migrations/v004_recaps.py` and advance the ordered ladder to v4;
  do not smuggle a current table into the legacy bootstrap SQL or rely on
  `CREATE TABLE IF NOT EXISTS` during every open.
- **It reaches the dashboard with no new channel.** `watched_mtime` walks
  `.dreamwork/` including `ledger.sqlite3` and its `-wal`, so a recap write moves
  `/mtime` and the next `collect()` re-derives. Nothing new to build.

A third store was considered and refused: it would buy nothing the ledger store
does not already give, and it would be a fourth thing to open, migrate and back
up.

The current composition seam is
`dreamwork_db.store.dreamwork_store_spec`: one `StoreSpec` registers `tasks`,
`questions`, and `reviews` and applies `initialize_legacy_store`. Add a
`dreamwork_db.recaps.RecapRepository` beside those repositories. Keep
`task_store_spec` and `question_store_spec` as compatibility delegates and do
**not** create a rival `recap_store_spec`. Reads use a short
`open_database(..., Access.READ)` snapshot; writes use
`open_database(..., Access.WRITE)` plus `handle.transaction()`. The dashboard
consumes a repository DTO, never SQL or `sqlite3.Row` in `watch.py`.

Shape, with the attempt lifecycle being the point rather than an afterthought:

```sql
CREATE TABLE recap_attempt (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  beat_at            TEXT NOT NULL,
  due_at             TEXT NOT NULL,
  deadline_at        TEXT NOT NULL,
  started_at         TEXT NOT NULL,
  finished_at        TEXT,
  status             TEXT NOT NULL CHECK (status IN
                       ('running','ok','unchanged','no_source','digest_error',
                        'runner_error','timeout','invalid_output')),
  recap_text         TEXT,
  detail             TEXT,
  source_session_id  TEXT,
  source_cursor_from INTEGER,
  source_cursor_to   INTEGER,
  records_examined   INTEGER,
  events_selected    INTEGER,
  events_elided      INTEGER,
  diagnostics_count  INTEGER,
  model              TEXT NOT NULL,
  every_n            INTEGER NOT NULL CHECK (every_n > 0),
  prompt_bytes       INTEGER,
  prompt_sha256      TEXT,
  projector_version  INTEGER NOT NULL,
  duration_ms        INTEGER,
  exit_code          INTEGER,
  runner_log_path    TEXT,
  UNIQUE (beat_at),
  CHECK ((status = 'running') = (finished_at IS NULL)),
  CHECK ((status = 'ok') = (recap_text IS NOT NULL)),
  CHECK (recap_text IS NULL OR length(CAST(recap_text AS BLOB)) <= 2048)
);
```

Note the timestamps: transcript records are **UTC with a `Z`** while the loop's
own files are local. Every comparison in the runner is in UTC and every render
is local. Getting this wrong is a silent ten-hour error on this host.

`runner_log_path` is free forensics — `ccc` prints its run directory on stderr
(`>> ccc:output-log >> …/runs/grok-…`), and `#686`'s lesson is that the cheap
path leaves nothing else behind.

After acquiring the target-scoped lock, insert and commit `running` **before**
reading the transcript or starting `ccc`; finalize that row with an
`UPDATE ... WHERE id = ? AND status = 'running'` in a second transaction. A
process death therefore leaves an overdue fact rather than no attempt. A DB
failure starts no model, advances no source cursor, and cannot escape into the
heartbeat pipe. Preserve the core's typed `Busy`, `Corrupt`, `SchemaMismatch`,
`ConstraintViolation`, `ValidationError`, `Conflict`, and `DatabaseError`
outcomes instead of flattening them into prose.

**The runner never touches this table, the repo, or git.** Its entire contract
is *argv in, text on stdout*. The Python wrapper owns persistence. That is what
keeps `#686` — a `ccc @glm52` run that produced eight files and committed
nothing — from having an analogue here: this model is given no work to leave
behind. It is also what makes "configurable" a one-line change rather than a
plugin system.

---

## 7. The scheduling seam

This is the decision I was most torn on, so here is the IGC.

**Context:** the heartbeat is a long-lived `heartbeat 4.75m '<msg>' | python3
tick_line.py --target <t>` inside one `Monitor`, armed per session
(`initialization.md:103-108`). Measured live: heartbeat 1.9 MB, tick_line
10.8 MB, both children of the agent process. 40% of 285 s = **114 s**.

| Idea | All | G1 | G2 | G3 | G4 | G5 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| I1 second Monitor, plain `heartbeat 4.75m` | ✘ | ✘ | ✔ | ✔ | ✔ | ✔ |
| I2 second Monitor, aligned `heartbeat @4.75m+1m54s` | ✘ | ✘ | ✔ | ✔ | ✔ | ✔ |
| **I3 a `tee` leg on the existing pipeline** | **✔** | ✔ | ✔ | ✔ | ✔ | ✔ |
| I4 a pass-through filter doing the work on a thread | ✘ | ✔ | ✘ | ✔ | ✔ | ✔ |
| I5 the tick turn schedules a detached `sleep 114; run` | ✘ | ✔ | ✔ | ✘ | ✘ | ✔ |
| I6 a `watch.py` daemon thread polling `last_tick` | ✘ | ✘ | ✔ | ✔ | ✔ | ✔ |

- **G1** fires at 40% *of the actual beat* and stays there · **G2** cannot delay
  or break the loop's wake · **G3** fires while the agent is mid-increment or
  idle · **G4** at most one run in flight, without asking the `#675` probe ·
  **G5** off means no model process starts

The decisive errors:

- **I1 ✘G1.** `heartbeat`'s plain mode sets `fire_at = now + interval`
  (`heartbeat.py:287`) — it is free-running, anchored to whenever it was armed.
  Two such timers share no clock, so "1.9 minutes later" is true on day one and
  arbitrary by day three. An independent timer can hold an *offset*; it cannot
  hold a *phase*.
- **I2 ✘G1.** Aligned mode does anchor (to local midnight) and does support a
  native `+offset`, so this looks right — but 86,400/285 = **303.158**. The day
  does not divide by the period. A `@4.75m+1m54s` companion truncates its last
  beat at 23:56:24 while the main timer's last is 23:59:15, so **once a day one
  beat gets no recap and one gets it at the wrong phase**. And today's live
  heartbeat is *plain*, so an aligned companion would be offset from arm-time by
  a constant nobody chose. Switching the main heartbeat to aligned would fix the
  anchor but changes the loop's wake schedule, which is yours to decide, not
  mine.
- **I4 ✘G2.** Putting the work on a thread inside a filter in the wake pipeline
  means a crash in recap code kills the wake. `tick_line.py` holds the invariant
  that no failure in it can cost the loop its wake; I am not willing to create a
  second file that has to hold it.
- **I5 ✘G3, ✘G4.** It depends on the agent taking the tick turn promptly — a
  tick consumed fifteen minutes into an increment schedules late or not at all,
  and a compaction turn eats it outright. It also accumulates detached
  `sleep` orphans, which is `#203` with a new source.
- **I6 ✘G1.** `watch.py` has no scheduler and no idea when the beat fired; it
  would have to poll `status.json`'s `last_tick`, inheriting coordinator
  bookkeeping as a dependency — and that field is measurably unreliable right
  now (`last_tick` 16:24, `updated_at` 02:58, actual time 21:27). It also
  re-execs on every source edit under `--dev`, so its phase resets constantly
  while anyone is working on this repo.

**Survivor: I3.** The Monitor command gains one leg:

```
heartbeat 4.75m '<msg>' \
  | tee --output-error=warn-nopipe >(python3 <skill-dir>/recap_tick.py --target <t>) \
  | python3 <skill-dir>/tick_line.py --target <t>
```

`recap_tick.py` reads a pulse, drains any further buffered pulses without
acting on them (skip, never queue), sleeps 114 s, runs one recap, and returns to
reading. Phase-locked by construction, including on a late beat, because it is
reading *the beat itself* rather than a second clock. Serial by construction, so
G4 needs no process probe — which is the honest answer to `#675`: this design
does not ask that question, so that bug does not block it. A lockfile is still
wanted, but only against a *second monitor* being armed (`#673`'s migration
hazard), not against self-overlap.

Two things to verify before writing this, not after: the Monitor's shell is
`/usr/bin/zsh -c` (measured), so `>(…)` is available — but that is harness
behaviour and could change, and `--output-error=warn-nopipe` is what stops a
dead recap leg from killing `tee` and with it the wake. If either fails, it
fails toward *no recap and a working heartbeat*, which is the right direction.

**Timing budget, which is what sets the timeout:** 114 s offset + a run must
finish before the next beat at 285 s. That leaves 171 s; take 120 s as the
timeout and keep 51 s of margin. Measured worst case at the cap was 24.6 s, so
120 s is five times the observed need. The kill must be `killpg` on a
`start_new_session` group — measured, `ccc` is **7 processes**, and killing the
`ccc` pid alone leaks the tree at ~240 MB.

**Why 40% is the right offset,** since you asked for it and the reason should be
stated rather than assumed: the beat is when the coordinator does its tick work
— reading the ledger, syncing status, dispatching. A recap fired *at* the beat
describes a state mid-change, and pays its 240 MB on top of the tick's own cost.
At 114 s the tick's work has settled, the recap describes something that is
true, and the two costs do not overlap. It also lands roughly half a beat before
the next one, so a hung run is dead long before the next fires.

---

## 8. The feature gate and the runner config

### 8.1 The current convention

`SKILL.md` now defines the experiment gate: one tracked `.dreamwork/<name>`
file, **absent means off**, with its format documented in `file-formats.md` and
validated by `lint.py`. The recap follows that convention directly; it is not a
plugin, environment toggle, or `enabled:` field inside an always-present file.

### 8.2 Shape and behaviour

Tracked `.dreamwork/recap`:

```
model: glm52
every: 1
```

The file is absent by default. When present, `model` is a ccc alias in a narrow
identifier grammar and `every` is a bounded positive integer (`1` means every
beat). Missing, unknown, duplicate, or invalid values are a config error: no
model starts and the dashboard names the error. Re-read the file every pulse,
so deleting it turns the feature off without restart.

There is deliberately no arbitrary `runner:` shell string. The v1 adapter
constructs fixed argv, `ccc -y @<model>`; changing the model remains data,
without making a tracked config file a command-execution surface.

Honest limit, stated rather than glossed: with the gate off, the ~11 MB
`recap_tick.py` process still sits reading the pipe. The **runner** never
spawns, which is the cost that matters and the thing the brief asked for, but
"off" is not literally "no process". Removing the `tee` leg from the Monitor
command is the harder off-switch; it needs a re-arm to take effect, which is why
it cannot be the everyday one.

**How you turn it off:** delete `.dreamwork/recap`. It takes effect on the next
beat; no model process starts after the absent gate is observed.

---

## 9. The transition

You said *"transition when updated"*, and there is a genuine collision to
surface rather than paper over.

`transitions.md` is opt-in by default — *"motion is soft, slow, and never
crisp-mechanical. It is also strictly opt-in — most state changes do not
animate"* (`:225-226`) — and its closed list of what animates ends *"Nothing
else animates"* (`:255`). More pointedly, the repo's own precedent for a
tick-re-rendered dashboard text block is **explicitly no motion**, and it says so
in five places; `style.css:689-694` is the clearest: *"NO MOTION, and no
transition declared: this panel re-renders through innerHTML on every tick and
nothing about it is a gesture the page initiates"*.

Against that, a recap is not a value that ticks — it is a new sentence that
arrives every few minutes, and a page that swaps a paragraph under the reader
with no gesture at all is the snap-among-drifts that document warns about.

**Recommendation: it animates, using the existing `#559` content cross-dissolve
and nothing new.** `transitions.md:646-652` describes exactly this case — a
container that stays while its content is replaced, *"old values out as new
values in"* on a `.42s` envelope, *"one gesture one level down, never a second
idiom"*, reduced motion snapping the swap. The implementation is
`bdContentSwap(el, freshHTML)` at `client/router.js:2843` plus
`client/style.css:589-611`. Reusing it verbatim is the whole point: inventing a
recap-specific fade would be the second idiom that rule forbids.

Three bindings, and the first is the one that would actually bite:

1. **Gate on `recap.id`, never on the tick.** The dashboard re-renders every 2 s;
   a recap changes every ~4.75 min. Ungated, the gesture replays about 142 times
   per recap — *"motion with nothing behind it"* (`router.js:2834-2836`, the
   `#151` rule). `bdContentSwap` has a text-equality short-circuit, but two
   consecutive recaps of a quiet loop can be byte-identical, and re-dissolving
   identical text *"says a change happened where none did"*.
2. **First paint and reload settle visible**, never replaying the arrival
   (`transitions.md:470-473`).
3. **Reduced motion snaps the swap** — a hard contract (`transitions.md:695-699`).

I have filed this as a question anyway, because the counter-precedent is five
code sites, and "transition" could reasonably mean "the value changes" rather
than "it animates".

---

## 10. Open questions

Filed in `.dreamwork/questions.md` under `## Open` as one entry with three
questions, each carrying a `rec`:

- **`Q1` — the gate's home.** The now-documented convention makes a tracked,
  absent-means-off `.dreamwork/recap` file the recommendation (§8). This remains
  his question to confirm; the convention does not answer it on his behalf.
- **`Q2` — cadence.** Every beat is 303 runs/day. Every second beat halves it and
  doubles the window, which the cap absorbs. Rec: every beat while you are
  watching it, `every: 2` as the knob that lets you back off without a code
  change. §7.
- **`Q3` — motion.** Confirm the `#559` cross-dissolve, given that
  `transitions.md`'s default for this panel shape is no motion and five code
  sites say so. §9.

---

## 11. What could go wrong

**The stale recap.** The failure that matters is a dashboard showing a
four-hour-old recap that looks exactly like a four-minute-old one — `#136` in a
new place. So: every attempt writes a row, including the ones that produce
nothing. The dashboard distinguishes off; no attempt; `running`; fresh `ok`;
judged `unchanged`; failure before any success; failure after success; overdue
`running`; and config/DB unavailable. A newer failure makes old prose stale
immediately, while `unchanged` refreshes the judgement without inventing new
prose. The attempt id, displayed recap id, generated/checked times, age, and
failures-since-success come from the repository DTO rather than client policy.

**The compaction boundary.** Handled in §4: the transcript keeps everything, so
the recap keeps reading actions; the summary blob is dropped by an exact field
test rather than a heuristic; the boundary is surfaced because it is worth
seeing. The residual risk is that the harness changes the field names — which is
why the projector should count what it dropped and a run that crosses a boundary
it *cannot* identify should say so, not proceed quietly.

**The runner dying.** `#686` is the standing evidence that a `ccc @glm52` process
can run to completion and produce nothing. Worse, `dogfood-orchestration.md`
records that *"a lane that dies before its first token is indistinguishable from
one that ran and reported nothing"* — a 401 gives zero bytes on **both** stdout
and the run log, with the error on stderr only. So: stderr is captured and its
tail stored (never `/dev/null`), exit code stored, `empty` is a distinct status
from `error`, the 120 s timeout kills the **process group**, and `ccc`'s own run
directory is recorded from stderr so there is something to read afterwards.

**The cost.** Memory is the scarce resource here, not CPU — swap is at 55 of
62 GB. A run is 238–257 MB across 7 processes for 19–25 s, once per 285 s: a
duty cycle of about 8%, time-averaging to ~20 MB. That is affordable against
25 GB of free RAM. What makes it affordable is the timeout, which is a *memory*
control before it is a latency control: without it a hung run converts an 8%
duty cycle into a permanent quarter-gigabyte, and the serial consumer means a
second one can never start on top of it. Tokens are ~1.5k in and ~150 out per
run, ~0.5M in per day on a cheap model.

**The exposure I am not going to pretend away.** The digest is command lines,
file paths and assistant text from your session, sent to an external provider
every few minutes, unattended. That is not new in kind — `@glm52` lanes already
get the whole repo — but it is new in *cadence*, and the digest goes on **argv**,
so it is visible in `ps` and in `pgrep -af ccc` output while the run lasts. The
repo already abridges long ccc argv (`occupied.py`), and `ARG_MAX` is 2 MB
against a 24 KiB prompt, so nothing breaks; it is a disclosure, not a defect.

---

## 12. What I would build first

Increments that each land and revert alone, in an order where the early ones are
useful without the later ones:

1. **`recap_digest.py` alone** — transcript in, capped and elided digest out, on
   stdout. No model, no database, no dashboard. This is where all the subtlety
   lives (source resolution and its refusal, the compaction rule, the elision
   marker, UTC) and none of the risk. **It is useful by itself**: run it and read
   what the agent has been doing, with no model involved at all. Testable against
   a fixture transcript, including a synthetic compaction boundary.
2. **The v4 migration and `RecapRepository`** — register it in
   `dreamwork_store_spec`, including the committed `running` attempt and final
   compare-and-set transaction. Still no model.
3. **`recap_tick.py`** — the gate, the runner invocation, the timeout with
   `killpg`, and the terminal statuses. Ships with `.dreamwork/recap` absent.
4. **The dashboard read** — the `collect()` key, its mandatory
   `SUMMARY_ALLOWED`/`SUMMARY_DENIED` classification (a new key that is in
   neither reds by design, `watch.py`), and the render with its four
   states. **No motion yet.**
5. **The transition** — `bdContentSwap` keyed on `recap.id`, reduced-motion
   parity, and a guard that proves the gesture fires once per recap and not once
   per tick.
6. **Arming** — the `tee` leg into `initialization.md`, a `migrations/` entry
   (this is a state-shape change affecting existing targets), and the live
   monitor swapped. `#673`'s lesson applies exactly: a monitor armed before this
   keeps firing the old pipeline **and looks completely normal doing it**, so the
   dashboard must be able to say "no recap ever arrived" rather than showing
   nothing.

Steps 1 and 2 together are the smallest honestly useful version.

---

--- SUMMARY ---

- **What it is.** Every heartbeat, ~114 s after the beat, a small Python wrapper
  projects the last few minutes of the main agent's own JSONL transcript into a
  one-line-per-step digest, hands it to a cheap model on argv, and stores the
  resulting 2–4 sentences in a new `recap` table in `ledger.sqlite3`. The
  dashboard shows the newest one. Proven end to end tonight: a real
  `ccc -y @glm52` run over your live session produced an accurate recap in 19 s.

- **A blocking defect found.** `status.json` has **no `agent_session` key**, so
  nothing says which transcript is the main agent's — and the obvious derivation
  from the target directory points at a file two days stale, because the live
  session sits under a *worktree* slug. The design refuses and says so rather
  than guessing; the missing key is a `#665` regression worth its own task.

- **Compaction is handled by not being fooled by it.** The transcript is never
  truncated, so a digest of `tool_use` records reads actions on both sides of a
  boundary. The 15–24 KB `isCompactSummary` blob is dropped by exact field test,
  and the boundary is replaced with a visible marker — so the recap never starts
  recapping a summary, and "the agent just compacted" becomes information
  instead of a silent distortion.

- **Cap 24 KiB of prompt, head 1/3 + tail 2/3, middle elided with a marker
  naming the count, span and volume.** Derived, not picked: one beat measures
  6.2 KB, so elision only starts after ~4 missed recaps. The marker is what lets
  the model say "and ~1,200 further steps" honestly instead of inventing them —
  verified over a 3-hour window that crossed two compactions.

- **The ledger store, not the journal.** Gitignoring does not discriminate (both
  are). Add a v4 migration and `RecapRepository` to the canonical
  `dreamwork_store_spec`; do not create raw SQL in `watch.py`, a second store,
  or a recap-only spec. Existing DB/WAL mtime polling reaches the dashboard.

- **Scheduling: a `tee` leg on the existing heartbeat pipeline** (IGC over six
  candidates). An independent timer can hold an offset but not a *phase* —
  heartbeat's plain mode is free-running, and its aligned mode breaks once a day
  because 4.75 min does not divide 24 h. Reading the beat itself is the only
  option phase-locked by construction. Serial by construction, so "is one
  already running?" never needs the `#675` probe. Timeout 120 s, killing the
  **process group** (a `ccc` run is 7 processes, ~240 MB).

- **Gate: a tracked `.dreamwork/recap` file, absent means off.** It carries only
  bounded `model` and `every` data; the ccc argv is fixed, not a configurable
  shell string. The resident sidecar may still read pulses while off, but it
  starts no model and opens no WRITE handle.

- **Motion: reuse `#559`'s cross-dissolve, gated on `recap.id` not on the tick**
  — otherwise the gesture replays ~142× per recap. Flagged as a question because
  `transitions.md`'s default for a tick-re-rendered panel is *no motion*, said
  explicitly in five code sites, against your "transition when updated".

- **Failure is designed, not discovered.** A committed `running` row precedes
  transcript/model work and is finalized transactionally, so death leaves an
  overdue fact. `unchanged`, source, digest, runner, timeout, and invalid-output
  outcomes stay distinct; stderr is captured because a 401 leaves zero bytes
  elsewhere. Old prose cannot look current after a newer failure.

- **Cost: ~8% duty cycle, ~20 MB time-averaged, ~0.5M cheap tokens/day.** The
  timeout is a memory control first: without it a hung run makes a quarter-gig
  permanent, and memory — not CPU — is what is scarce on this host.

- **Build order:** the digest builder alone first (all the subtlety, no risk, and
  useful by itself with no model at all), then the table, then the runner behind
  its gate, then the dashboard read, then the motion, then the arming. Steps 1–2
  are the smallest version worth having.
