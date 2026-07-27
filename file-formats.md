# File formats — what the loop writes, and what reads it back

Some files under `.dreamwork/` are written by the loop in prose and read
back by a tool. For those, "what the file means" is not enough: the
reader has a shape it requires, and a file that misses it fails
**silently**, because zero parsed entries is indistinguishable from
nothing to report.

That is not hypothetical. On 2026-07-25 a dreamwork instance on another
project opened its dashboard to zero questions over a `questions.md`
holding six, four of them genuinely open and two of those privacy
defaults. The loop had written `##` headings *as* the questions. Nothing
told it otherwise, because the only specification of the format lived in
the parser.

**Rule: if you write a file something else parses, write it in the shape
below. If the shape is not stated below, say so rather than inventing
one — an invented shape that looks right is exactly how this fails.**

## `.dreamwork/answers.md`

Optional, read by `watch.py` for `/answers` and written by POST `/ask`. Missing is
calm; the first successful ask atomically creates the skeleton.

```markdown
# Questions for the dreamer

## Open

- **2026-07-26 — Human-authored question title** Human-authored context.

## Answered

- **2026-07-26 — Human-authored question title** → answered (2026-07-26 13:00):
  Loop-authored resolution.
```

The headings are literal `## Open` and `## Answered`; entries reuse the shared
`- **Title** body` grammar. Direction is distinct from `questions.md`: Open is
always authored by the human and asks the dreamer. To answer, the coordinator
writes a loop-attributed `→ answered (<timestamp>): <resolution>` at the start
of the body, moves the entire entry (including any body/thread) from Open to
Answered, and leaves its human-authored title and question intact. Reopening is
not an MVP state: create a new linked question which names the prior title.
There is no dreamer-answer HTTP endpoint in this increment.

## `.dreamwork/questions.md`

Read by `watch.py` for `/questions`, the open-question badge, and the
`/answer` and `/comment` write paths. The single most important format
in the loop, because it is the channel to the human.

```markdown
# Questions for the human

## Open

- **2026-07-25 — a question, whose bold title may hard-wrap across
  source lines and closes its `**` wherever that falls.** The body is
  indented prose. Backticked paths like `.dreamwork/review/x.html`
  become links.
  - **Note (human, via watch, 2026-07-25 09:00):** a threaded note.
    Continuation lines belong to the note, not the body.
  - **Follow-up (loop, 2026-07-25 09:01):** one from the loop.
  - **Answer (via watch, 2026-07-25 09:02):** answered from the page,
    awaiting the loop's fold.

## Answered

- **A folded question.** → resolved (2026-07-25): the resolution head
  comes first in the body, and `answered_at()` reads only that.
```

Load-bearing details, each of which was a bug at some point:

- **The section headings are literal.** The reader matches
  `line.strip() == "## Open"` and `== "## Answered"` exactly. No other
  line opens a section — this is what the other project got wrong.
- **A top-level `- **` always starts a new entry**, and nothing can
  absorb it: not an unterminated title, not an open sub-bullet.
- **Titles may hard-wrap.** The loop writes at ~72 columns, so a title
  running onto the next line is normal input, not malformed.
- **Sub-bullets may hard-wrap too**, and their continuation lines belong
  to the bullet rather than the body.
- **Author tags are a closed set**, and the page renders them
  differently: `(human, via <channel>, <ts>)` and `(loop, <ts>)` are the
  current forms; `(via watch…)` reads as human and `(in-session…)` as
  loop, kept for entries written before the tags existed.
- **Sub-bullet ORDER is chronological, and the page relies on it** (#128).
  A note written before the answer renders above it; one written after
  renders below. Append — never insert a note above an answer that
  predates it, or the card will say he replied to himself.
- **The `<ts>` in a tag is read, not decoration.** `YYYY-MM-DD` with an
  optional ` HH:MM`, inside the tag's parentheses. It is rendered beside
  the author label, so a wrong one is a wrong claim on screen; an absent
  or unparseable one renders nothing, which is fine. A date in the
  *note's own text* is never mistaken for it.
- **A note or answer is ONE paragraph, wrapped at ~72 columns with a
  4-space continuation indent** — and every continuation line is indented
  and never begins a bullet. This is not tidiness, it is the reason the
  file can be trusted (#146). Human text arrives from a textarea he
  pastes into; written at column 0, a pasted `- **…**` becomes a
  top-level entry by the rule above, and the loop reads a question he
  never asked. A continuation line that merely *starts a bullet* is
  nearly as bad: it ends the note's capture, so the rest of his words
  fall into the entry's **body** and read as the loop's own prose.
  `human_block()` in `watch.py` is the only correct way to write one; do
  not hand-format human text into this file.

  The reader joins a sub-bullet's continuation lines back into one string
  before anything renders it, so folding the newlines costs nothing
  visible — the wrapping is for whoever opens the file in an editor.

Canonical, exercised example — every shape above appears in it:
`dev/capture/fixture/.dreamwork/questions.md`. Read that before
inventing anything.

**Getting the shape wrong is no longer silent** (#136). The dashboard
distinguishes three kinds of zero: no file (a quiet line), the seeded
skeleton or everything answered (nothing at all — the real all-clear),
and *content the reader cannot see*, which is announced in the page's
one warning colour and names this path. `lint.py` says the same thing
from the command line. So a file in the wrong shape now costs a red
light rather than a morning.

## Priority on a question (#197)

An entry title may begin with `P1 · `, `P2 · ` or `P3 · `. **Absent means
P2** — the middle band, deliberately, so an explicit `P3` sorts genuinely
below an unmarked entry rather than level with it.

`P1` blocks work · `P2` wants an answer soon · `P3` whenever. Same
vocabulary as the task ledger, because he already reads P1-P3 there and a
second scale would be one to learn.

It is part of the title, so it needs no parser change and it renders — he
sees the priority on the card rather than only in the sort. **"Oldest
first on a tie" is free**: the file is already chronological, so a
*stable* sort by priority alone produces it. Do not add a date
comparison; that would be a second mechanism able to disagree with the
first.

`lint.py` errors on one thing, stated as an outcome rather than a pattern:
**a title that reads as prioritised and does not sort that way.** That is
the quiet failure — the entry he most wants seen sits mid-list looking
urgent. A title with no marker is normal and says nothing.

It reaches that outcome in two shapes, and they are one mistake to whoever
typed the title (the marker did not take):

- a band **outside** the three (`P4 · `, `P0 · `);
- a legal band with a **separator the parser does not accept** (`P1: `,
  `P1·`, `P1 - `). The message names the fix, because "P1 is wrong" reads
  as nonsense to someone who just typed a perfectly good P1.

**The band is asked of `watch.py`'s `title_priority`, never re-derived in
the linter** — the same move as the plugin-command check reading core kinds
from `COMMANDS`. That is not tidiness. This check shipped holding its own
copy of the marker rule, and the copy was the more permissive of the two:
`P1: `, `P1·` and `P1 - ` were each blessed by the linter and read as
unmarked by the page, so the checker was blind to its own stated failure in
three of the four ways a human would most plausibly write it. A check and
the thing it checks cannot hold separate copies of one rule and stay
honest.

## `DREAMWORK.md` frontmatter — the version stamp (#194)

The file may open with a YAML frontmatter block; when present, it carries
the skill version this target last reconciled with:

```
---
dreamwork-version: 5853e1789929
---
# DREAMWORK.md — <project>
```

- **`dreamwork-version`** (required once the block exists): exactly
  twelve hex chars, or the word `unknown`. It is the **first token** of
  `bin/ud-dw-githash` output — the `+N` dirty annotation is live state,
  never stored, because identity that changes with an uncommitted edit
  would make every comparison miss.
- The upgrade check at init compares this against what `ud-dw-githash`
  prints now; a difference means commits landed in between, and the
  discovery pass reads them (plan: `docs/plans/version-and-upgrade.md`).
  The stamp therefore *lags by nature* — it records the last
  reconciliation, not the newest commit.
- **No frontmatter is legal** (every pre-#194 target) and lints as a
  WARN, not an error. The rest of the file below the closing `---` stays
  entirely the human's prose — the block is the only machine-read part.
- Other keys are tolerated with a WARN so the contract grows
  deliberately; lines that are not `key: value`, an unclosed block, a
  truncated sha, or a block missing `dreamwork-version` are errors.

Checked by `lint.py` (`check_dreamwork_frontmatter`), which is the only
code reader today; the init step reads through the same grammar.

## The rest

These are written by the loop and read by something. Where a row says
`lint.py`, the check is executable and you can stop reading — run it.
Where it says prose only, follow the shape already in the file rather
than restructuring it, and prefer appending to an existing skeleton.

| File | Read by | Contract | Checked |
|---|---|---|---|
| `.dreamwork/tasks.md` | humans today; the dashboard once #98 lands | One `- **#N**` entry per task; `Next id: **N**` in the header. Ids are **permanent**, so a duplicate is unrecoverable and `Next id` must exceed every id present. Origin is recorded forward-only from #216 — the section below | `lint.py` |
| `.dreamwork/status.json` | `watch.py`'s status reader; **`dreamhub.py`** | Valid JSON, and now an interface — see below | `lint.py` |
| `.dreamwork/watch-port` | `just deploy`; **`dreamhub.py`** | One line, an integer port. Written once and then persistent: it is the address the human's bookmark points at, so changing it silently strands him | `lint.py` |
| `.dreamwork/watch-tint` | `watch.py`, in **every** window open on this project | One line: one name from `watch.py`'s `TINTS`. Absent means the default. An unknown name is ignored **silently** — the page falls back and nothing on screen says his choice was dropped | `lint.py` |
| `.dreamwork/run-mode` | `watch.py` dashboard + the coordinator/main dreamer on tick and via `watch-events.log` | One line: one name from `watch.py`'s `RUN_MODES` (`lackadaisical`, `hot`, `assisted`). Absent/unknown → `lackadaisical`. Machine-local, **gitignored** — operational posture, not a portable project default. `status.json` may mirror it later but never owns it | `lint.py` |
| `.dreamwork/submissions.log` | recovery — the loop, and him, after something failed | One JSON object per line, written as the FIRST act of `do_POST` before any parsing or validation. Append-only, never rewritten. Machine-local, **gitignored** — see below | `lint.py` |
| `.dreamwork/plugin-commands.json` | `watch.py`'s composer (#86) | `{"commands": [{kind, label, desc, plugin}]}`. Written **whole** by the loop at plugin resolution, never appended — see below. Machine-local, **gitignored** | `lint.py` |
| `.dreamwork/skill-version` | init's update check | One line naming a real file in `migrations/`. A name that does not exist there makes every migration read as pending | `lint.py` |
| `.dreamwork/dreams/<date>-<time>-<slug>.md` | the coordinator; grooming | The **filename** is the contract: `2026-07-25-1130-slug.md`. It carries the ordering | `lint.py` (naming) |
| `.dreamwork/lessons.md` | humans; the loop at init; grooming | **Stated in the file's own header** — a claim you could read alone, then the case that earned it. Craft belongs where the writer already is | prose only |
| `.dreamwork/watch-events.log` | the coordinator's monitor — **it wakes on a line and acts on it** | One event per line. Human text written into it must not be able to forge a record: collapse newlines before they reach the file | prose only |
| `DREAMWORK.md` | the loop, the wizard, the scope gate | Section headings are load-bearing — the scope gate and the goal chain both address them by name | prose only |
| `~/.cache/agent-comms/<target>/coord-inbox.md` | the coordinator's tail monitor | Append-only, one report per line, prefixed `[agent-name]`. Machine-local, never committed | prose only |
| `~/.cache/agent-comms/<target>/<agent>-inbox.md` | that subagent, **between increments** | Append-only. Write it with `relay.py` — body from stdin so it cannot be shell-expanded, stamp from the clock so it cannot be invented | prose only |

## `.dreamwork/tasks.md` — origin, forward-only from #216 (#213)

Who filed a task is a fact. Before this contract the ledger almost never
wrote it down, and a fact that was never written cannot be reconstructed
later without guessing — so the rule looks only forward, and the past
stays honestly unknown rather than retroactively classified.

**Every entry whose leading `- **#…**` token names any id >= 216 carries
exactly one origin marker** in its `·`-separated metadata chain:

```
origin: **human**      filed on the human's steer
origin: **loop**       filed by the loop itself
origin: **unknown**    never recorded — the truthful value for anything
                       filed before the convention existed
```

`unknown` is a first-class value, not a failure and not a gap to tidy:
it is the only honest mark for post-cutoff ids that predate this
contract, and writing it is a statement, not an omission.

The load-bearing decisions, each of which a narrower reading would get
wrong:

- **The enforcement key is every numeric id in the entry's leading bold
  token; the rule fires when ANY of them is >= 216** (equivalently, when
  the highest is). Combined entries are therefore governed on either id:
  `- **#250/#251**` and `- **#292/#293**` carry a marker (`unknown` —
  they landed before the convention), while `- **#138/#156**` predates
  the cutoff on both ids and stays unmarked. A combined landed summary
  written after the cutoff about pre-cutoff tasks is NOT retroactively
  governed by the writing date — only by the ids it numbers.
- **A `#N` in the body is a cross-reference, never the entry's number.**
  `blocked on #264` must not govern the entry that contains it, or most
  of history would suddenly owe a marker.
- **Entries whose ids are all < 216 are not checked at all.** Historical
  tasks may omit origin (absent reads as historical unknown), and a
  pre-cutoff entry quoting the convention in its prose — #213's own
  entry quotes `origin: **human|loop**` as its spec — is prose, not a
  marker. Forward-only means the linter does not even look.
- **An entry is a list item opening `- **#…**` plus its indented
  continuation lines.** The column-0 prose summaries under Recently
  landed are not entries and never join one.
- **The marker may hard-wrap** — `origin:` ending a line, the value
  opening the next — because the loop writes at ~72 columns; the linter
  joins the entry's lines before reading, the same allowance the
  questions.md title rule makes. #288 and #252 both wrap this way.

`lint.py` (`check_task_origins`, inside `check_tasks`) errors on a
governed entry with no marker, a marker whose value is outside the three
(wrong case included — `**Human**` is a claim a reader would have to
interpret, and interpreting is guessing), or more than one marker (two
claims is none). The error names the entry and the vocabulary, because
"origin is wrong" reads as nonsense to someone who never met the rule.

Rendering human/loop/unknown coverage on the dashboard (#217) is its
own increment and deliberately NOT here. First-sight parsing (#216) HAS
landed — see the next section.

## `.dreamwork/tasks.md` — first-seen origin from git history (#216)

`task_origins.py` answers "who filed each task" as a fact about the
task's ARRIVAL, never about its current text. It walks the ledger's own
git history oldest-to-newest and classifies every numeric id from the
FIRST snapshot where that id appears in a leading `- **#…**` token:

```
python3 task_origins.py --repo <target> [--path .dreamwork/tasks.md] [--json]
```

stdout is JSON either way (pretty by default, single-line with `--json`):
`{repo, path, history_complete, history_note, tasks}` where each task is
`{id, origin, first_commit, first_seen, title}`, sorted by id. Exit is
nonzero ONLY for real repo/path/git errors — not-a-checkout, an absolute
or `..`-escaping `--path`, git itself failing. A missing ledger is a
truthful empty `tasks`, not an error.

The load-bearing rules, each of which a reader of the CURRENT file would
get wrong:

- **First sight is final.** Only that snapshot's explicit marker speaks:
  `human` and `loop` are accepted; missing, invalid, wrong-case, or
  duplicated markers fail closed to `unknown`. A later edit — including
  backfilling a marker — never retroactively classifies the arrival.
  Commit author and message are never consulted.
- **Combined entries classify every id in their leading token** from that
  one entry; an id first seen separately and earlier keeps its earlier
  record. A `#N` in a body is a cross-reference and classifies nothing.
- **A deleted task stays in the output** — grooming cannot un-happen an
  arrival. **Pre-cutoff ids are parsed too**: the cutoff governs the
  linter's demands, not history's coverage.
- **The grammar is imported from `lint.py`** (`ledger_entries`,
  `ORIGIN_MARK`), not re-copied — a second copy of one rule is how the
  priority check drifted. A malformed snapshot fails closed to `unknown`
  for its affected entry and never crashes the walk.
- **A shallow clone reports `history_complete: false`** with a
  `history_note`, rather than silently describing a later edit as the
  arrival.

#217 will render this; nothing in this module is a UI.

## What stays unguarded, and why

An honest inventory, because a list of what IS checked implies coverage
it does not have (#150).

- **The inbox files have no check at all.** They are append-only prose
  read by a language model, so there is no shape to violate — but that
  also means a malformed or misdirected relay fails silently. `relay.py`
  removes the two failures that actually happened (shell expansion,
  invented timestamps) by construction rather than by checking.
- **Delivery is unguarded and probably unguardable.** The inbox is
  durable but not delivered: an idle agent never reads it, and nothing
  can tell a silent agent from a silent channel. The mitigation is
  procedural — write, then wake — not a check.
- **`lessons.md` and `DREAMWORK.md` are prose by intention.** Their value
  is in being written well, and a linter would only ever check the parts
  that do not matter.
- **Nothing verifies that a relay was UNDERSTOOD**, only that it was
  written. Every coordination failure this loop has had was of that
  shape, and it is the reason reports say what durable state changed
  rather than "done".


## `.dreamwork/watch-tint` is HIS, not the loop's

It is the first file under `.dreamwork/` recording a PREFERENCE rather
than a state, and that is why it is committable and why it is *not* an
events-log event: the log's contract is one line per thing an agent then
acts on, and a colour is not one. Logging it would wake the loop to do
nothing. The loop learns his choice by the file being in the repo, the
same way `DREAMWORK.md` works.

## `.dreamwork/run-mode` — pace for the main dreamer (#290)

One line, closed vocabulary, trailing newline — the same physical shape as
`watch-tint` / `watch-port`, with the opposite commit rule:

```
hot
```

- **Authoritative** for the main dreamer's run mode. `collect()` exposes it
  as `run_mode` so every open window converges on the existing `/mtime` poll.
  `status.json` is an ephemeral loop claim and must not be the sole store.
- **Selectable v1:** `lackadaisical` (default; idle-friendly, no proactive
  fan-out), `hot` (continuous bounded work, coordinator-only), `assisted`
  (hot plus a few disjoint helpers under existing ownership rules).
  **`hierarchical` is not a legal file value** — the dashboard shows it
  disabled until #264 concurrency and #288 containment make it honest.
- **Gitignored / machine-local.** Operational posture on this host, not a
  surprising project default for the next clone. Targets gain the ignore
  line via `migrations/2026-07-27-01-run-mode.md`.
- **Dual-write on change only.** `POST /run-mode` with `{ "mode": "…" }`
  validates against `RUN_MODES`, atomically writes the file, and appends one
  `watch-events.log` line shaped `run-mode via watch[ /path]: <mode>` when
  the mode actually changes. Identical final → 200, no event, no needless
  wake. The dashboard arms a **shared 10s pending** selection across tabs
  (localStorage keyed by absolute `data.target`); every change resets the
  countdown; only the final mode is POSTed.
- **Consumption honesty.** This file + the events line are how an agent
  learns the mode. Reading them does not, by itself, change a running
  session's scheduler unless that session's monitored-event / skill protocol
  says so — do not claim otherwise.

Checked by `lint.py` (`check_run_mode`), reading the closed set from
`watch.py` so the checker cannot drift from the page.

## `.dreamwork/submissions.log` — his words, before anything can lose them

Written because they were being lost. `_handle_answer` logged the question
*title* and the destination, never the text he typed, and it logged
**after** the write and only on success — so an entry that failed to match
returned 409 and recorded nothing anywhere. `append_answer` returns
unmatched on a hard-wrapped title, which is exactly what #116 was. He
typed an answer, got an error, and the words were gone.

So: **one line per request received, written as the first act of
`do_POST`** — before dispatch, before parse, before validation. One call
site rather than four, so a handler added later cannot forget, and every
400/404/409/413/500 still leaves his text on disk.

| key | | |
|---|---|---|
| `t` | required, string | `%Y-%m-%dT%H:%M:%S` local — deliberately the same stamp `watch-events.log` uses |
| `path` | required, string | the POST path as received (`/answer`, `/comment`, `/command`, `/tint`, …). **Not a "kind"** — deriving one means parsing, and parsing is the step this file exists to survive |
| `bytes` | required, int | the declared `Content-Length` |
| `req` | any JSON value | the body, when it parsed |
| `raw` + `why` | strings | instead of `req` when it did not. `raw` is the body decoded with `errors="replace"`; `why` is `"json"` (valid UTF-8, not JSON) or `"decode"` (not valid UTF-8) |
| `truncated` | optional, `true` | only when the body exceeded the 20,000-byte cap (then rejected 413, first 20,000 bytes kept). **Absent otherwise, never `false`** |

**Exactly one of `req` / `raw`; `why` is present iff `raw` is.**

**Why `req` rather than the raw body always**: `json.loads` then
`json.dumps` round-trips every value faithfully, so nothing of his is
lost, and the line stays greppable and readable instead of holding a
doubly-escaped string where every newline in his answer is a literal
`\n`. The verbatim form is kept for the case that actually needed it.

**A torn LAST line is a WARN, not an error.** A crash mid-append is
precisely the situation this file exists for, and going red on it would
mean the linter shouts loudest at the moment the log did its job. A
malformed line anywhere else IS an error — that is a broken writer, not a
dead process.

**This log is the only VERBATIM copy of what he typed.** Every accepted
write elsewhere is a *rendering*: `append_answer` hard-wraps his text to
the file's line width, so even a success stores his words reflowed. The
guard for this file learned it by failing — it searched questions.md for
a sentence that had landed, and the file held it broken across lines.
Anything that needs his exact bytes (recovery, re-scanning, an audit of
sent-vs-recorded) reads this file, never the rendered ones. That is the
difference between a backup and a duplicate.

**Never committed.** It holds his raw typed text; `.gitignore` carries it
(and the fixture copy) alongside `watch-events.log`. An upgrading target
gains that line via `migrations/2026-07-25-15-submissions-log.md` —
without it the file sits untracked, one `git add -A` away from pushing
his words somewhere.

Shape credit: dreamer-qsec, #199, who read the handlers first and sent the
contract before either half was built — which is why this row describes
the file rather than a guess at it.

## `.dreamwork/plugin-commands.json` — why the loop writes it at all

A plugin declares its commands in its own SKILL.md, for humans and agents
to read. This file is the loop copying them where the composer can see
them, and it exists because of one asymmetry: **`watch.py` reads the
target.** It is invoked `--target <project>` and its whole model is that
what it shows lives under that root. Plugin skills do not — they sit in
`~/.claude-p/skills/`, `~/.agents/skills/`, and elsewhere, varying by
harness and by machine. A composer that read the plugin's own files would
work here and silently show nothing on the next machine.

Three properties, each of which is a failure mode turned into a rule:

- **Written whole, never appended.** Unloading a plugin is then the
  *absence* of a write rather than a remembered deletion. Same move as
  fold-by-complement and `human_block()`: make the mistake unavailable
  instead of forbidding it.
- **Machine-local, so gitignored.** Which plugins resolve, and which
  version of each, is a property of the machine — the same reason the
  composer cannot read them directly. A committed copy would be another
  target's truth.
- **No `common` field.** Core commands own the composer's main row; a
  plugin's land in the `...` menu. A plugin cannot promote itself into
  the most valuable real estate on the page, so loading one can never
  degrade the composer for the human.

`lint.py` refuses a kind that shadows a core command, a kind in the core
namespace, a duplicate, and — cross-read against DREAMWORK.md's Plugins
section — a command whose plugin is not loaded. That last one is the
stale-menu case: an entry the human can send that nothing answers. When
DREAMWORK.md has no Plugins section the check WARNs rather than errors,
because silence there is not a claim that nothing is loaded.

## `.dreamwork/status.json` — now an interface

It had one reader and a loose contract, which was fine: a single reader
and its writer co-evolve, and nothing breaks in between. On 2026-07-25
`dreamhub.py` became a second reader, and **a file with two readers is
an interface whether or not anyone wrote one down.**

Every field is **optional**, and readers must degrade rather than throw —
a fresh loop writes a nearly empty file, and a target whose loop is not
running still has to appear in the hub. Writers should provide the core:

| Field | Type | Means |
|---|---|---|
| `task` | string | one line: what the loop is doing right now |
| `goal` | string | the session goal this serves |
| `agents` | array of objects, each with at least `name` | live subagents; a reader shows the count and the names. Optional per agent: `in_flight` (one line: what it is doing right now — **the one subfield with two readers**, promoted into `watch.py`'s agent glance and republished by `dreamhub.py` in `/hub.json`, so treat it as load-bearing); `owns` (array of strings — the files it holds; `dreamhub.py` renders it as `name (owns)`, and a non-list renders as none); `kind` (`utility` when it is not a dreamer); and `awaiting_result` when it was dispatched and has not reported — a dispatched-but-silent agent is otherwise legible only from the coordinator's memory, which is exactly how two deliverables were lost (#144). **This list is a menu, not a whitelist** (#310): `watch.py` folds every agent key it does not name into "the rest" on purpose — *"Whatever is LEFT, not a second known list"* — so an unlisted field is still shown, and nothing here is safe to prune on the grounds that no reader names it |
| `queue` | object, integer `in_progress` and `pending` | queue depth |
| `awaiting_human` | array of strings | **non-empty means the human is the bottleneck.** The one field a reader must never bury (#130, #141) |
| `last_tick`, `last_commit` | string | freshness; a stale `last_tick` is how a stalled loop is spotted |
| `deploy`, `monitors`, `coordinator_next` | strings / arrays | recovery notes for whoever picks the loop up after a compaction |
| `push` | object: `at`, `channel`, `ok`, `detail` | **the loop's push-channel health** (#190). The loop writes one on every attempt, success or failure. `at` is ISO8601 with offset, from the system clock (never memory — the page renders it as an age); `channel` names what carried the push (`attn`, `PushNotification`, …); `ok` is a strict bool the renderer branches on; `detail` is the short reason a human acts on (the 403, the credit message). **Three states are distinguishable from the data:** no `push` key (never tried), `ok:true` (last landed), `ok:false` (last failed) — and only the last earns pixels. `ok:false` is a truthful runtime claim, not a broken file, so it lints clean; only a wrong TYPE is an error. Subfields are a menu like the top level (#310): the loop may grow the object, and nothing here rejects an unlisted key |

The file is **gitignored ephemera** and stays that way. It describes a
running process, so a committed one would be a lie the moment it landed;
that is also why there is no history to compute stats from (#142).

## `.dreamwork/.status-keys` — the only file `lint.py` writes (#303)

One key per line, sorted, `#` comment lines and blanks ignored on read.
It records which top-level `status.json` keys **this target has been seen
to carry**, and it exists because a projection missing a key is
indistinguishable from one that never had it: a coordinator's wholesale
rewrite dropped `retired_today` — fifteen lanes' retirements — and lint
called the result clean.

Three properties, each load-bearing:

- **Gitignored**, beside the gitignored file it describes. The tracked
  alternative was tried and refuted: `file-formats.md`'s field table above
  does not name `retired_today`, so it would have missed the exact incident
  that filed this, and treating it as required would red-flag every fresh
  target whose status.json is nearly empty by design.
- **Append-only.** Union of keys ever seen, never auto-shrunk. The obvious
  implementation re-records the current set each run, which makes the first
  run after a bad rewrite adopt the reduced set as its baseline — one
  warning, in the same run as the mistake, then silence. A check that goes
  quiet about a live loss looks exactly like a check that found nothing.
- **A human edit is the only way to accept a retirement.** Deleting the
  line is the deliberate act; nothing the loop does can.

This is the one place `lint.py` writes, and that cost is real — it was
read-only until #303. It is paid here and nowhere else: a write failure
WARNs rather than raising, so a read-only checkout still lints.

## `.dreamwork/docs/doc-map.md` — the one row that is a list (#307)

Every row in the doc map names a file, so the row cannot drift from what
it describes. One row names a **directory** and then enumerates its
contents in prose, and that one goes stale by itself: on 2026-07-27 it
listed 8 plans while `plans/` held 14, so six plans existed that a reader
of the map had no way to learn about. Nobody parses prose, so nobody
noticed.

The enumeration stays — detail is ranked, never withheld, and a map whose
answer is "run `ls`" has stopped being a map — which makes it a shape
rather than a sentence:

    | `.dreamwork/docs/plans/` | Active feature plans, alphabetical (a, b, c) | … |

- The row starts `` | `.dreamwork/docs/plans/` | `` at the start of a line.
- Somewhere in its description cell is a parenthesised, comma-separated
  list of plan **stems** — filename without `.md`.
- That set equals the set of `*.md` stems in `.dreamwork/docs/plans/`.

`lint.py`'s `check_doc_map_plans` WARNs in both directions: a stem on disk
and not in the row is undiscoverable, and a stem in the row with no file
is a typo or a plan that landed and was pruned from the directory but not
from the prose. Alphabetical order is stated in the row so an addition has
one obvious place to go.

## Browser-side storage — not files, still contracts

Two of his things live in the browser rather than under `.dreamwork/`: a
half-typed draft (#163) and the client's record of every submission (#175).
They are in this file for the same reason everything else is — **recovery is a
reader**. The whole point of #175 is that someone (him, or an agent walked
through it) can open devtools and get his words back, and that is impossible
without the key names and the value shape written down. A store nobody can find
is the silent shape, one storage layer over.

**Why the browser and not a file**, since #143's tint made the opposite call
and the two look identical from a distance: a tint is a setting *about* the
project and should follow it to another machine, so it is committable. A draft
and a submission log are **his words, unsent or possibly unlanded** — writing
them into the repo would publish them. So they stay on this machine, in this
browser, and never travel.

**Both partition on `data.target`** — the absolute project path the server
reports, never the project *name*. Two checkouts can share a basename, and his
draft surfacing under the wrong loop is worse than a lost one.

**`localStorage['dw:draft:<target>']`** — the composer's unsent draft.

```json
{"t": "the text in the box, verbatim", "k": "add-idea"}
```

`k` is a command kind from the live vocabulary; it is validated on the way back
in, because a plugin's command can disappear between sessions and sending his
words as the wrong kind is worse than defaulting. Written on every `input` with
no debounce, removed when the box is emptied by hand, and cleared on a
successful send **and on nothing else** — not on close, not on blur, not on a
rejected POST, which are the moments he most needs it back. One key per project
holds the *most recent* unsent thought: he runs several windows, and a restore
never overwrites a box that already has text in it, so only the stored copy is
last-write-wins.

**IndexedDB `dw-submissions:<target>`, store `subs`** — every submission this
browser made, with how it ended.

```json
{"id": 7, "at": 1784969517618, "path": "/answer", "kind": "answer",
 "title": "the question title, or null for a command",
 "text": "what he typed", "from": "/questions",
 "outcome": "ok", "status": 200}
```

- `id` — autoincrement, the store's own order and the reading order.
- `at` — epoch ms at the moment of **send**, not of outcome.
- `path` — the POST route; any future route is recorded the day it is added.
- `kind` — the act in his terms: `answer`, `note`, or a command kind.
- `outcome` — `pending` → `ok` | `rejected` | `unreachable`. Written as
  `pending` **before** the request, so a tab that dies mid-POST leaves a record
  saying exactly that. An entry is never deleted, and never rewritten except to
  attach the outcome it was waiting for; one that stays `pending` is a true
  statement rather than a gap to tidy.
- `status` — the HTTP status, `0` when nothing answered.

**One database per project, not one database with a `project` column.** A
column needs every reader to remember to filter by it, and a reader that forgets
returns another loop's submissions while looking perfectly correct.

Read it with `window.__dwSubmissions()`, which resolves to every record for the
current project; the composer's history panel (#165) is the same data rendered.

**Checked by the browser guards, not by `lint.py`** — `dev/capture/draft.mjs`,
`subslog.mjs` and `history.mjs`. That is a real difference in kind and not a
gap being excused: the linter reads files on disk and cannot reach a browser
profile, so these contracts are verified by driving the page rather than by
parsing. If you change a key name or a field here, the guard that fails is one
of those three.

## Why this file exists rather than a paragraph in SKILL.md

SKILL.md says what each file *means* and when to write it. That is the
right thing for it to say, and it is what made the failure possible: a
loop can follow every semantic instruction perfectly and still produce
something the reader cannot see. The shape lives here so there is one
place to correct when a reader changes.

This file is the explanation; **`lint.py` is the enforcement**, because a
checker cannot drift from itself the way a third description can (#137).

```
python3 <skill-dir>/lint.py --target .
```

It imports `watch.py` and runs the *real* parsers rather than
reimplementing them, so a clean pass means the dashboard can genuinely
see the file — not that it matches a second opinion about the format.
Init runs it at step 9. ERROR means a reader cannot see what is there;
WARN means worth knowing but not broken (an absent file on a fresh
target is the usual case). It degrades rather than crashing when
`watch.py` is mid-edit by another agent, reporting entries as unverified
instead of claiming they are fine.
