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

## The rest

These are written by the loop and read by something. Where a row says
`lint.py`, the check is executable and you can stop reading — run it.
Where it says prose only, follow the shape already in the file rather
than restructuring it, and prefer appending to an existing skeleton.

| File | Read by | Contract | Checked |
|---|---|---|---|
| `.dreamwork/tasks.md` | humans today; the dashboard once #98 lands | One `- **#N**` entry per task; `Next id: **N**` in the header. Ids are **permanent**, so a duplicate is unrecoverable and `Next id` must exceed every id present | `lint.py` |
| `.dreamwork/status.json` | `watch.py`'s status reader; **`dreamhub.py`** | Valid JSON, and now an interface — see below | `lint.py` |
| `.dreamwork/watch-port` | `just deploy`; **`dreamhub.py`** | One line, an integer port. Written once and then persistent: it is the address the human's bookmark points at, so changing it silently strands him | `lint.py` |
| `.dreamwork/skill-version` | init's update check | One line naming a real file in `migrations/`. A name that does not exist there makes every migration read as pending | `lint.py` |
| `.dreamwork/dreams/<date>-<time>-<slug>.md` | the coordinator; grooming | The **filename** is the contract: `2026-07-25-1130-slug.md`. It carries the ordering | `lint.py` (naming) |
| `.dreamwork/lessons.md` | humans; the loop at init; grooming | A bolded claim readable on its own, then the concrete case that earned it, then its source. Prune once a lesson has graduated into a guardrail or a check | prose only |
| `.dreamwork/watch-events.log` | the coordinator's monitor — **it wakes on a line and acts on it** | One event per line. Human text written into it must not be able to forge a record: collapse newlines before they reach the file | prose only |
| `DREAMWORK.md` | the loop, the wizard, the scope gate | Section headings are load-bearing — the scope gate and the goal chain both address them by name | prose only |
| `~/.cache/agent-comms/<target>/coord-inbox.md` | the coordinator's tail monitor | Append-only, one report per line, prefixed `[agent-name]`. Machine-local, never committed | prose only |
| `~/.cache/agent-comms/<target>/<agent>-inbox.md` | that subagent, **between increments** | Append-only. Write it with `relay.py` — body from stdin so it cannot be shell-expanded, stamp from the clock so it cannot be invented | prose only |

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
| `agents` | array of objects, each with at least `name` | live subagents; a reader shows the count and the names. Optional per agent: `kind` (`utility` when it is not a dreamer), and `awaiting_result` when it was dispatched and has not reported — a dispatched-but-silent agent is otherwise legible only from the coordinator's memory, which is exactly how two deliverables were lost (#144) |
| `queue` | object, integer `in_progress` and `pending` | queue depth |
| `awaiting_human` | array of strings | **non-empty means the human is the bottleneck.** The one field a reader must never bury (#130, #141) |
| `last_tick`, `last_commit` | string | freshness; a stale `last_tick` is how a stalled loop is spotted |
| `deploy`, `monitors`, `coordinator_next` | strings / arrays | recovery notes for whoever picks the loop up after a compaction |

The file is **gitignored ephemera** and stays that way. It describes a
running process, so a committed one would be a lie the moment it landed;
that is also why there is no history to compute stats from (#142).

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
