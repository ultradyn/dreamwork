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

**Both write paths replace it atomically** (`atomic_write_text`: temp,
`fsync`, `os.replace`, parent `fsync`) — never by opening it in plain
write mode. That is a durability contract, not a preference: opening it to
write truncates it first, so anything that stops the write before the flush
loses every question he ever asked and every answer he ever gave. It was
written the truncating way until #370, and the correct helper had been
thirty lines above it the whole time, in use by `/ask`. A failed write must
leave the file byte-identical and no `.questions.md.*.tmp` behind.

```markdown
# Questions for the human

## Open

- **2026-07-25 14:32 — a question, whose bold title may hard-wrap across
  source lines and closes its `**` wherever that falls.** The body is
  indented prose. Backticked paths like `.dreamwork/review/x.html`
  become links.
  - **Note (human, via watch, 2026-07-25 09:00):** a threaded note.
    Continuation lines belong to the note, not the body.
  - **Follow-up (loop, 2026-07-25 09:01):** one from the loop. A loop
    follow-up that *retires* part of the ask rewrites the body smaller
    instead of appending — `~~struck~~` for a withdrawn sub-question,
    with one line saying when and why, and the reasoning parked
    elsewhere (human-set 2026-07-29 00:54; a `#449` amendment grew the
    entry to 4368 characters to explain a refuted premise, and the live
    question was below it).
  - **Answer (via watch, 2026-07-25 09:02):** answered from the page,
    awaiting the loop's fold.

## Answered

- **A folded question.** → resolved (2026-07-25): the resolution head
  comes first in the body, and `answered_at()` reads only that.
```

**The resolution head goes in the BODY, never inside the title** — and the
title is allowed to wrap, which is what makes this a trap rather than a
typo. `parse_answered` takes the entry's title as its bold span and
`answered_at()` reads only what follows, so a `→ … (date)` that lands inside
a wrapped title is structurally invisible: the entry renders as never
resolved, and the `#411` undated-entry WARN reports it as a *dropped* marker
when it was in fact written. Three of the five undated entries found on
2026-07-29 were this, and the repair hit it twice — the first attempt
inserted the head inside `#264`'s wrapped title and the entry stayed
undated. `lint.check_resolution_marker_outside_title` ERRORs on it, and
fires on the marker's **position**, never on the wrap: 30 of 65 titles wrap
legitimately.

**The resolution head goes ABOVE every sub-bullet** — at the head of the
body, before the first `- **Answer …` / `- **Note …` line (#467). A sub-
bullet absorbs every following non-bullet line as its own wrapped
continuation (`_parse_entries` invariant 3; only a blank line or a plain
`- ` bullet releases it), so a `→ answered (…)` written after a sub-bullet
is swallowed into that sub-bullet's text and never reaches the body:
`answered_at()` returns None, the fold looks done, and the #411 WARN names
a *dropped* marker for one that was written, just in the wrong place.
Measured 2026-07-29 folding the `#445` answer; moving the marker above the
answer line fixed it instantly. `lint.check_resolution_marker_after_subbullet`
ERRORs on it, keyed on the parser's truth — an entry offends
when `answered_at` sees no marker AND the marker text is found inside an
absorbed sub-bullet — so a blank-line-released marker, however odd it
looks, is legal.

### Title date and optional time (#392b)

The bold title opens with an optional priority (`P1 · ` / `P2 · ` / `P3 · `),
then a **date**, then an optional **local clock time**, then ` — ` and the
rest:

```text
- **P2 · 2026-07-28 07:54 — how long has this been waiting?**
- **2026-07-25 — a date-only title still legal**
```

| shape | written | age the dashboard claims |
|---|---|---|
| **timed** | `YYYY-MM-DD HH:MM` | two figures from that local time (`00h 24m ago`) — exact to the minute |
| **date-only** | `YYYY-MM-DD` | one figure, or the word `today` for same calendar day — honest day precision (#392a) |

**Write the time going forward.** The dashboard ages a question from what is
in the title; there is no second clock. A date-only title is still legal and
is not a fabrication — it is just day-resolution — but a fresh ask whose
wait time matters must carry `HH:MM` (24-hour, local, same shape as the
`<ts>` already used in note/answer tags). Do not invent a time for history;
do not rewrite live entries to add one. Do not put a `git log` call on the
request path to recover a missing time — that was measured at ~18ms per
entry / ~1.7s for the full file and is wrong for `/data.json`.

The title date is still not a sort key (priority alone sorts; see #197). The
time is for the age display only.

**What an ask must contain (#421, answered 2026-07-29 01:17 — `rec`: A+B+D).**
These are contract, not style, because each one exists to stop a specific way
an ask has silently failed here:

- **A — the ask comes first.** The decision and its accepted answers lead the
  entry; evidence follows. An ask whose question sits below its reasoning gets
  read as a report, and he answers what he found first.
- **D — state what a valid answer looks like.** Every entry ends with its
  accepted answers (`rec` · named options · free text · `not yet`). Answering
  should not require inventing the shape of the reply. `rec` is only offered
  where a recommendation is actually stated.
- **B — an unanswered sub-decision is recorded, and a fold that drops one is an
  error.** A multi-part ask (C1/C2, Q1/Q2) can be half-answered, and half is
  the dangerous state: `#275`'s Q3/Q5/Q6 have been unanswered since 2026-07-25
  with nothing noticing. `lint.py` owns making that loud. Recognising a
  sub-decision is **declared, not guessed from prose** — the corpus labels
  decisions `Q1`/`M1`/`S1`/`C1` in freeform text, and inferring them is the
  half-working-regex failure this repo distrusts most. So a multi-part ask
  carries ONE canonical declaration line, and only that line is read:

  ```text
  **Sub-decisions:** `Q1`, `Q2`, `Q3`
  ```

  Backticked `<Letter><digits>` tokens, comma-separated (the same backtick-
  comma shape `**Ask: \`C1\`, \`C2\`…**` already uses). `lint.check_subdecisions`
  reads **only** that line — never prose — and **ERRORs** when a folded
  (Answered) entry's resolution does not name every declared label. A label is
  resolved if it appears backticked or bold anywhere in the folded entry
  outside the declaration line, which covers the `→ answered`/`→ resolved`
  head, a `Rec **Q1**` decision, and an `Answer (…)` bullet in one rule. A
  fold that carries a sub-decision forward NAMES it in the head
  (`→ answered (…): rec on Q1; Q2/Q3 carried forward`), so naming-it is both
  the resolution and the record — **there is no second store**. History
  handling is the marker itself: an entry that does not declare is not
  examined, so the whole pre-rule corpus stays silent and clean, and scope is
  content-resolved without a sha pinned by hand. `#275`'s own open Q3/Q5/Q6
  are the motivating defect (they sit unanswered with no nudge to close);
  this check catches the *future* fold that would drop them.
- **An update makes the entry smaller** (2026-07-29 00:54). When a sub-question
  dies — refuted, superseded, settled — `~~strike~~` it or cut it, with one
  line saying when and why, and park the reasoning in the ledger or
  `lessons.md`. Every line left standing is a line he must read to find the
  live question.
- **No length gate, ever** (2026-07-29 01:13/01:17). Steer style with
  descriptors — precise, detailed, concise, dense — and plan the words in
  advance so an ask *can* be short. A word estimate is advisory
  (*"aim for under 200 words"*); nothing passes or fails on length, and no
  check measures it. `#421`'s own word-count claim had already broken twice
  against its own corpus before it was withdrawn.

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
  - **Closed means closed, and getting the word wrong deletes the bullet
    in silence** (#343). The renderer matches an exact prefix
    (`watch.py`'s `NOTE_TAGS` / `ANSWER_TAGS`), so anything else is not a
    contribution at all: it falls into the entry BODY and renders as a
    `·` item with its raw tag visible as text and **no author label** —
    the #340 defect, reached by a one-word typo.
  - **The two channels are spelled asymmetrically, which is the trap.**
    His is `Note (human, …)`. The loop's is **`Follow-up (loop, …)`** —
    *not* `Note (loop, …)`, *not* `Reply (loop, …)`, *not* `Answer
    (loop, …)`. All three of those read perfectly reasonable and match
    nothing. `Answer (via watch…)` is **his** and the loop must never
    write it; there is currently no loop-authored *resolution* tag at
    all, which is a gap #254's design records rather than papers over.
  - Every one of those wrong spellings has actually occurred here:
    `Answer (loop, …)` was the #254 bug, `Note (loop, …)` was written on
    a P0 question an hour after that was explained, and **three
    `Reply (loop, …)` bullets sat unrendered in the live file** until
    `lint.check_author_tags` found them — measured through the real
    parser, fixing them recovered 3 contributions (28 → 31).
  - That check **WARNs** on a dated bolded bullet whose prefix is in
    neither tuple, and it **imports the tuples from `watch.py` rather
    than restating them**: a second copy of the tag list is a second
    thing able to disagree with the renderer, and disagreeing with the
    renderer is the entire defect. It matches a single leading word, a
    timestamp inside the parentheses, and a colon after them — narrow on
    purpose, because prose like `- **Four early asks, all applied
    (2026-07-25)** —` is not a tag and one wrong WARN per run teaches the
    reader to skip the right ones.
- **Sub-bullet ORDER is chronological, and the page relies on it** (#128).
  A note written before the answer renders above it; one written after
  renders below. Append — never insert a note above an answer that
  predates it, or the card will say he replied to himself.
- **A second `Answer (via watch…)` is retained, never overwritten** (#446).
  The reader used to keep one answer per entry, so a second answer
  replaced the first and his earlier words were gone at parse time —
  before any render rule ran, and with nothing recording that it
  happened. questions.md is the durable record of what he decided, and
  the loop cannot know what it forgot, so every answer bullet is kept,
  each with its author tag and timestamp, in file order. The parser does
  not rank or interpret (amendment, correction, or a genuine second
  answer to a re-opened entry): it retains what he wrote, and the loop
  reconciles semantics at fold. The **first** answer is the thread's
  resolution anchor (the position the card cuts the discussion around);
  a later answer rides the same awaiting-fold rail beneath it. This is
  the existing thread grammar — timestamped contributions in file order
  — not a second one.
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
| `.dreamwork/tasks.md` | humans today; the dashboard once #98 lands | One `- **#N**` entry per task; a combined head `- **#N/#M**` is a single entry naming every id in its ids-only bold span, and both ledger readers (`watch.parse_ledger`, `lint.check_ledger_sections`) count every id — so `#7/#8` is two ids in one entry, not one. `Next id: **N**` in the header. Ids are **permanent**, so a duplicate is unrecoverable and `Next id` must exceed every id present. Origin is recorded forward-only from #216 — the section below | `lint.py` |
| `.dreamwork/status.json` | `watch.py`'s status reader; **`dreamhub.py`** | Valid JSON, and now an interface — see below | `lint.py` |
| `.dreamwork/handoffs.md` | the coordinator's tick; `watch.py`'s status panel; `lint.py` | Append-only. **Section order is `## Folded` then `## Pending`** so an EOF append lands under Pending (the instruction is true). Id grammar: plain `#N`, sub-id `#Na`, or combined `#N/#M` in the bold head. Pending line: `- **#…** · landed \`<sha>\` [\\\`<sha>\\\`…] · <ts> · by <claimer> — what` — one **or more** backticked shas (#415); a task landing in two commits is the ordinary case. Folded line: `- **#…** → folded (ts): …` (the note cites the landing sha in prose — `citing \`sha\`` / `merged \`sha\`` — read by correlation). Nothing moves; correlation is by (id, sha) (#409): a fold citing a sha a Pending landed consumes only that sha; a fold whose cited shas match no Pending falls back to id-only. Sub-id/combined normalise to parent digit id(s) against `## Open`. A bolded-id line in the wrong section or with an unrecognised head is malformed (loud), never silent | `lint.py` |
| `.dreamwork/watch-port` | `just deploy`; **`dreamhub.py`** | One line, an integer port. Written once and then persistent: it is the address the human's bookmark points at, so changing it silently strands him | `lint.py` |
| `.dreamwork/watch-tint` | `watch.py`, in **every** window open on this project | One line: one name from `watch.py`'s `TINTS`. Absent means the default. An unknown name is ignored **silently** — the page falls back and nothing on screen says his choice was dropped | `lint.py` |
| `.dreamwork/run-mode` | `watch.py` dashboard + the coordinator/main dreamer on tick and via `watch-events.log` | One line: one name from `watch.py`'s `RUN_MODES` (`lackadaisical`, `hot`, `assisted`). Absent/unknown → `lackadaisical`. Machine-local, **gitignored** — operational posture, not a portable project default. `status.json` may mirror it later but never owns it | `lint.py` |
| `.dreamwork/posture` | the coordinator/main dreamer on tick (#445) | Three-axis override of run-mode's posture: `pace:`, `asking:`, `delegation:` — one per line, `#` comments allowed. Absent → derived from run-mode (see § below). Closed sets on pace/asking fail loud; delegation carries a number that steers, never gates | `lint.py` |
| `.dreamwork/submissions.log` | recovery — the loop, and him, after something failed | One JSON object per line, written as the FIRST act of `do_POST` before any parsing or validation. Append-only, never rewritten. Machine-local, **gitignored** — see below | `lint.py` |
| `.dreamwork/plugin-commands.json` | `watch.py`'s composer (#86) | `{"commands": [{kind, label, desc, plugin}]}`. Written **whole** by the loop at plugin resolution, never appended — see below. Machine-local, **gitignored** | `lint.py` |
| `.dreamwork/skill-version` | init's update check | One line naming a real file in `migrations/`. A name that does not exist there makes every migration read as pending | `lint.py` |
| `.dreamwork/dreams/<date>-<time>-<slug>.md` | the coordinator; grooming | The **filename** is the contract: `2026-07-25-1130-slug.md`. It carries the ordering | `lint.py` (naming) |
| `.dreamwork/lessons.md` | humans; the loop at init; grooming; **`dev/lessons_index.py`** (#349) | **Stated in the file's own header** — a claim you could read alone, then the case that earned it. Craft belongs where the writer already is. What the parsers rely on (#349): an entry is a `- ` bullet whose continuation lines are indented (or blank); its **first sentence** is the leading `**…**` span when present, else the text to the first full stop — the near-dup check compares only that sentence, the index classifies on the whole entry's own words | `dev/lessons_index.py` (read); `lint.py` (near-dup first sentences) |
| `.dreamwork/watch-events.log` | the coordinator's monitor — **it wakes on a line and acts on it** | One event per line. Human text written into it must not be able to forge a record: collapse newlines before they reach the file | prose only |
| `DREAMWORK.md` | the loop, the wizard, the scope gate | Section headings are load-bearing — the scope gate and the goal chain both address them by name | prose only |
| `~/.cache/agent-comms/<target>/coord-inbox.md` | the coordinator's tail monitor | Append-only, one report per line, prefixed `[agent-name]`. Machine-local, never committed | prose only |
| `~/.cache/agent-comms/<target>/<agent>-inbox.md` | that subagent, **between increments** | Append-only. Write it with `relay.py` — body from stdin so it cannot be shell-expanded, stamp from the clock so it cannot be invented | prose only |

## `.dreamwork/tasks.md` — the two section headings are unique and ordered (#440)

The ledger has exactly two sections, opened by literal heading LINES:
`## Open` then `## Recently landed`. Both are matched **anchored**
(`^[ \t]*## Open[ \t]*$` / `^[ \t]*## Recently landed[ \t]*$` — the patterns
`watch.LEDGER_SEC_OPEN` / `LEDGER_SEC_LANDED` compile), never by a bare
`text.split('## Recently landed', 1)`: the string `## Recently landed` also
appears **in the prose of open entries** (one quotes the very grammar that
reads it), and the unanchored split lands on the mention. That corrupted the
file twice on 2026-07-28 — a fold wrote a file with two landed headings and
130 lines in the wrong half, and a count returned 33 open entries instead of
142. Five hand-rolled ledger parsers have now been wrong here, against a file
whose production parser was importable every time.

The contract is three properties, each load-bearing:

- **Exactly one `## Open` and one `## Recently landed` heading LINE.** A
  second copy — a real heading, or a quoted one an unanchored reader mistakes
  for one — moves where every consumer thinks a section begins.
  `lint.check_ledger_sections` cross-checks the open-id count against
  `watch.parse_ledger` for this reason, and `dev/ledger.py assert_headings`
  refuses to fold or count a file that violates it.
- **`## Open` precedes `## Recently landed`.** The ledger is read as
  `(open, landed)` in document order; an inversion is not a valid ledger.
- **Locate the sections by the anchored heading LINE, never by substring.**
  `dev/ledger.py` (the one supported `fold` / `counts` path) reuses
  `watch.parse_ledger` for the id sets and the anchored patterns for the
  section boundaries, and asserts all three properties before AND after every
  write — the post-write assertion matters most, because both incidents had
  the symptom appear far from the cause.

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

## `.dreamwork/tasks.md` — an open entry whose work has landed (#323)

An entry under `## Open` may legitimately stay there after a commit says it
landed. Two real shapes: a task whose acute half shipped while its larger
scope remains (`#269`), and a task whose ask awaits the human's ruling,
because that ruling is part of its definition of done (`#275`, and `#306`
for why).

**Such an entry must NAME the commit** — the short sha, anywhere in the
entry body. That is the whole contract, and it exists because the
alternative has no signal: a genuinely stale open entry and a deliberate
partial are otherwise identical text, and three stale ones accumulated in
a single evening (`#314`, `#156`, `#315`) with nothing noticing. Citing the
sha is what `#269` and `#275` already did unprompted, so the rule writes
down an existing habit rather than inventing a marker.

`lint.check_landed_still_open` reads `git log` for subjects matching
`close(#N):` or `merge(#N):` — a convention this repo keeps rigorously —
and **WARNs** when an open entry's id has such a commit that the entry does
not name. It never ERRORs: a close commit is strong evidence, not proof, so
an error would make `#275`'s honest state unrepresentable. A target that is
not a git repository is skipped silently, because "cannot check" must not
read as "nothing to fix".

Do not reach for a prose keyword instead. It was tried and it is wrong:
`#315`'s body contained the word "landed" while describing the *problem*
(`#301 fixed the LANDED half`), so a keyword rule flags the stale case for
the wrong reason and cannot separate it from a deliberate partial.

## `.dreamwork/tasks.md` — a cited commit must resolve (#350)

The section above makes a cited commit load-bearing: an entry that stays open
after a landing proves it is deliberate by naming its sha. So the sha itself is
now parsed, and `lint.check_cited_shas` WARNs when one does not exist.

A **citation** is a landing keyword immediately introducing a backticked
7-40-character hex token, optionally through markup and an `at`/`in`/`as`:

```text
· landed `08cd931` ·            · **merged `7cdfc61`** ·
· **closed `d22fb09`** ·        · landed at `5c43a8f` ·
```

A bare `` · `abcdef1` · `` with no keyword is a **reference, not a citation**,
and is deliberately not checked.

**Cite the sha on the branch you merged INTO.** The hazard this exists for: an
agent reports the sha from its own worktree, and that commit is unreachable once
the branch is merged or rebased. `#302`'s entry cited `f0f4e2a` while the work
is at `08cd931`, and nothing noticed for a day — the citation is silent in both
directions, because a reader following it finds nothing and the check that reads
citations cannot tell a wrong sha from an honest one.

Two looser rules were tried and both are wrong, measured on the live ledger:

- **every backticked hex token** flags 94, of which 6 are pure-digit PIDs
  (`1246815`, `251691418`) that are valid hex. Requiring at least one `a-f`
  removes all six.
- **a landing keyword within 40 characters** still flags `fade326`, a c2c peer
  alias of seven hex digits, because the nearby keyword introduces the sha
  *before* it (``merged `7cdfc61`** (agent `fade326``). Proximity cannot tell
  which token a keyword belongs to.

If **every** cited sha is missing, the check does not warn — that is a fresh clone
or the wrong target, not a ledger that is entirely wrong — but it says so in an
OK row. Every exit from this check reports which exit it took, because four of
them used to be bare `return`s and one of them fired: the check skipped, left no
trace, and the flake it produced took twenty-five runs to characterise (#380).
"Cannot check" must never render as "nothing to fix", and silence is exactly how
it does.

## `.dreamwork/tasks.md` — a landing citation must not be a placeholder (#381)

A commit cannot cite its own sha, so the commit that lands work writes a slot and
a **follow-up** fills it in:

```text
· landed `PENDING` ·        →  · landed `12d17ad` ·
```

`lint.check_placeholder_citations` WARNs while the slot is unfilled. It is a WARN
and not an ERROR precisely because that intermediate state is honest and
unavoidable for one commit — erroring would block the commit doing the work. The
WARN exists for the follow-up, which was carried entirely by the writer
remembering, and twice on 2026-07-28 was not: `#362` read ``**LANDED `<pending>`**``
under `## Open` for hours and was found by accident while selecting an unrelated
task, invisible to `check_cited_shas` because a placeholder is not hex.

The recognised slot shapes are a **closed vocabulary** — `<…>`, `pending`, `tbd`,
`todo`, `xxx…`, `sha`, `hash`, `???`, `---`, case-insensitive. The looser rule
was tried first and is wrong: *a landing keyword introducing a token that is not
a sha* flags four things on the live ledger and none is a placeholder
(`questions.md`, `dev/capture/report.mjs`, `dither: "lsb-ign-v1"`, and a run of
prose). Precision 0-in-4, so the closure is the discrimination, and those four
tokens are pinned in the tests so nobody re-widens it to catch them.

## `.dreamwork/handoffs.md` — the delivery half of the single-writer rule (#381)

The ledger has **exactly one writer** (the coordinator), which is correct —
durable shared state wants a single writer or the next fan-out races it. The
gap this file closes is the other half: a foreign session that lands work it
does not own the ledger for previously had **no way to tell the writer**.
Its report died in its own session and the entry sat done-but-open until
someone happened to look. That cost an hour twice (#334, #362). This file is
the channel; `SKILL.md`'s tick step is the reader that consumes it; `lint.py`
is the check that surfaces an unfolded one to whoever runs it.

**Shape: append-only, never a rewrite.** The convention it follows is
`questions.md`/`answers.md`'s — literal `## ` section headings, a
`- **…**` entry head, and a `→ resolved (ts):`-style prefix for the
fold record — with one load-bearing difference: **nothing ever moves between
sections.** `## Folded` and `## Pending` each grow only by append. That is
the property the dreamer inbox has and a move-based shape would not: two
foreign sessions landing work at the same moment both append, and neither
can clobber the other's line. A rewrite that moved a Pending entry into
Folded would race a peer's append and lose it — exactly the lost-update the
single-writer rule exists to prevent, reopened one layer down.

**Section order (#406):** `## Folded` comes **first**, then `## Pending`. An
EOF append therefore lands under Pending, so the instruction "append under
`## Pending`" is true without rewriting. The older order put Folded last and
made a compliant `cat >>` land in the wrong section; a Pending-shaped line
under Folded was invisible to every reader until the malformed path ran
outside section scope.

**Id grammar (#401):** the bold head accepts the ledger's full vocabulary —
plain `#N`, sub-id `#Na` (one trailing letter), or combined `#N/#M` (and
longer `/`-chains). Correlation against `## Open` normalises to the parent
digit id(s) via `watch.handoff_parent_ids` — explicitly, not via
`ENTRY_ID`'s incidental letter-stripping. An unrecognised bold head, or a
well-formed line in the wrong section, is **malformed** (lint WARN), never
silent.

```markdown
## Folded

- **#362** → folded (2026-07-28 02:05): moved to Recently landed as `49c3c04`

## Pending

- **#362** · landed `ecc1f44` · 2026-07-28 01:39 · by dreamer-362 — the
  placeholder-citation check, red-proved against 4ce04e0
```

A **Pending** entry is one line and must state four things — the task id,
the **sha** that landed, **who** is claiming it (`by <claimer>`), and a
one-line `— what landed`. A **Folded** entry is the consumption marker: one
line naming the id and a `→ folded (ts):` note saying where it landed in the
ledger. Correlation is by **(id, sha)** (#409): a fold that cites a sha a
Pending landed — backticked in the note, `citing \`f2c950e\`` — consumes ONLY
that sha, so a second landing under the same id is not silenced by the first
one's fold. The fold-sha vocabulary is inconsistent by accident (most folds
cite the MERGE commit `merged \`cb476a7\``, not the work sha), so the
fallback is an **id-level** decision: when a fold's cited shas match no
Pending for that id, correlation falls back to id-only and a
legitimately-folded hand-off cannot resurface. Parent id(s) are still used
for the open-ledger WARN. The fold record is appended in the same increment
as the ledger move
(the coordinator's only act on this file besides reading), so a hand-off
marked folded while its task is still under `## Open` is a stale record, not
a normal state — and `lint.check_handoffs` WARNs on exactly that.

`lint.check_handoffs` reads `watch.parse_ledger` for the open/landed id sets
(the real parser, never a second copy) and WARNs on the one condition that
cost the hour:

- **a hand-off names `#N` as landed but `#N` is still under `## Open`** —
  the delivery signal, the whole point of the file. WARN, never ERROR: a
  freshly-landed hand-off is *supposed* to sit pending for the one tick
  before the coordinator folds it, so erroring would cry wolf on correct
  behaviour. The WARN is the nudge that makes the fold happen, carried by
  the writer remembering before and by nothing now.

A consumed hand-off (Folded names its id) is **silent, always** — even if
its task is still under `## Open`. That is the load-bearing choice and the
reason the fold record exists: a check that nags after you have complied
gets muted, and a muted check is worse than none. The fold record is the
coordinator's "I have seen this", and once it lands the hand-off stops
counting, by design. A hand-off whose task is already landed is silent too.
Missing file or empty sections: silent — a fresh target has none. The section headings are literal `## Pending` and
`## Folded`, matched exactly like `## Open`/`## Answered`, because a reader
that matches loosely is how a file full of entries renders as zero.

The dashboard surfaces the pending count in the status panel, reading this
file directly through `watch.collect` — a real reader, **not** a mirror of
`status.json`. `status.json` is a live process describing itself and the
loop's own claim; a hand-off is a foreign session's report of work the
ledger writer has not folded yet, and inferring liveness from surviving
artefacts is the wrong answer #363 proved by building it (#381). The
dashboard reads the file; the coordinator's tick reads the file; lint reads
the file. Three readers, one writer-append-each, no inference.

### Multi-sha hand-off (#415)

A task landing in **two commits is the ordinary case**: the fix plus a
follow-up (a lint count, a doc, a test the brief demanded). `#411` landed as
`54c68e8` (the fix) and `25a3fe4` (the lint count); the lane honestly wrote
both as ``landed `54c68e8` `25a3fe4``` and lint reported *a hand-off entry
the grammar does not recognise*. **The lane was right and the format was
wrong.** It was hand-normalised to the final sha with the other in prose,
which loses the structure: a tool can find the first commit no longer, only
a human reading the sentence.

The Pending line therefore accepts **one or more** backticked shas after
`landed`, space-separated:

```text
- **#411** · landed `54c68e8` `25a3fe4` · 2026-07-28 14:08 · by grok (wt/411) — …
```

Three decisions, each stated because the grammar is now a widening:

- **Order is written-order (landing first), not enforced.** The lane writes
  the shas in the order it made them, and nothing here reorders them. The
  first sha is the one that did the work; a later sha is a follow-up. lint
  does not assert the order — a hand-off is a report, and a reader that
  needed a specific order would be reading the wrong field (the ledger's
  `Recently landed` is where order is recoverable from `git log`).
- **No cap.** Two is ordinary; three has happened; capping at a number would
  re-introduce the exact defect this exists to fix (an honest N-sha landing
  rejected as malformed). A hand-off with no `by <claimer>` tail is still
  malformed, and that anchor — not a sha count — is what distinguishes a
  real entry from a garbled one.
- **A zero-sha hand-off is still malformed.** ``· landed · … · by <claimer>``
  states no commit, so the delivery signal (which commit landed) is empty.
  The widening admits two-or-more shas precisely because each names a real
  commit; zero names none. (One sha parses cleanly through the single-sha
  grammar and never reaches the widening path at all.)

`watch.py`'s `HANDOFF_PENDING_RE` and `parse_handoffs` accept the multi-sha
shape directly (#427). A pending row unpacks as `(id, sha, claimer)` where
`sha` is the **first** (landing) sha — so `lint.check_handoffs`'s existing
`for nid, sha, claimer in pending` needs no change — and also exposes
`.shas` for the full written-order list. `pending_handoff_records` returns
both `"sha"` (first) and `"shas"` (one-or-more) so the dashboard can read
every commit. A zero-sha line is still malformed (the RE requires one-or-
more backticked tokens).

`lint.py`'s multi-sha reclassification path (counted as
`multi-sha hand-off(s) recognised` when a line still lands in `malformed`)
is now a **no-op** for well-formed multi-sha Pending lines: they parse
cleanly and never reach `malformed`. The path stays as a safety net for
any residual mis-file, not as the primary grammar.

## `.dreamwork/tasks.md` — what marks a task landed (#399, #399b)

A task is **landed** when its id appears under `## Recently landed` in one of
three shapes:

```text
- **#395** — … · landed `abc1234` ·          the entry head lands #395
- **#5/#6** — … · landed `…` ·               a combined head lands both
- **#5** — … · also-landed: **#6, #7** ·     head + explicit multi-close
**#142** the ledger's own history, drawn (bb56f19) — …   historical inline
```

The fourth line is the **historical form**: a column-0 prose paragraph,
`**#N** <what landed> (sha)`, with no entry head and no `·`-fields, sometimes
several landings to a line. The ledger's older revisions are written this
way, and `ledger_series` walks them to draw the burndown, so a landed reader
that misses the form loses every completion older than the last groom — which
is how #399 re-reddened master, and why #399b reads it again.

**Every other bold id in a landed entry is a reference, not a landing.**
That means `related: **#367**`, `filed as **#392**`, and a prose
cross-reference in an entry's **indented body** (`see **#N**`,
`corrected (**#N**)`). #399 closed the hole those opened — the pre-#399
reader scanned every ids-only `**#N**` span, so the more correctly a landed
entry cross-referenced still-open work, the more open tasks it reported
done, and `check_landed_asks` told the coordinator to fold the human's
unanswered `#367` ask. `#399b` keeps that closed while reopening the
historical form: an entry's **indented continuation body is reference
territory** — that is where `related:`, `filed as`, and prose cross-refs
live, and the historical form has no such body, so it is pure column-0 prose
and every mention in it lands. A `related:` / `filed as` / `also-landed:`
field is excluded **by name** as well, so a marker written inline on a
one-line head (`- **#N** — … · related: **#X**`) cannot re-open the `#367`
hole. `related:` and landing read **different fields** or they disagree by
construction.

`also-landed:` follows the same field idiom as `related:` / `origin:`:
`·`-anchored, one bold span, comma-separated ids inside it. Mid-sentence
prose that merely *mentions* the words is not a claim (#395's class), and
neither is a bare `**#N**` that lives in an indented body.

`watch.parse_ledger` is the single reader of this rule (`_landed_ids`).

## `.dreamwork/tasks.md` — the ids-only bold span has ONE definition (#331)

The ledger packs several ids into one bold span three ways, and all three
have always been valid prose:

```text
**#5/#6**            slash
**#121 #123**        a blank run
**#157 + #222 + #223**   a plus, spaced
```

For a year only `/` was parsed, so every id in a space- or `+`-joined span
was invisible to every reader — 19 ids lost. `/` was widened twice (#301,
#315) and the defect simply moved to the next door, because three readers
each held their own copy. **Comma is not a joiner**: `**#392, #401, #405**`
is a prose list, not three ids, and it stays inert at the pattern level.
So does `**#96 stage 1**` (a section title), `**#392a**` (a sub-id), and
`**#501, #502**` (fictional ids quoted from a fixture).

The shape has **one definition**: `watch.IDS_ONLY_SPAN` is the ids-only
core, and every reader builds from it — `watch.LEDGER_ENTRY` (the entry
head), `watch.LEDGER_COMBINED_MENTION` (the same span, anywhere), and the
imports `lint.LEDGER_ID` and `status_sync.LEDGER_HEAD`. `lint.py` and
`status_sync.py` import the core rather than restating it, so a fourth
reader cannot be written wrong; `test_ledger_entry_rule_has_exactly_one_copy`
pins all three heads to one pattern and asserts both surface forms build
from the same core. Joiners are `[ \t]`, never `\s` — the ledger is
line-structured, and a span that could cross a newline would be a new bug.

## `.dreamwork/tasks.md` — `related:`, the relation that used to be a slash (#353)

For a year the ledger said "these two tasks are one piece of work" by writing
both ids in one title — `- **#250/#251**`. That is an **implicit** relation:
readable only by a human who notices the slash, and unrepresentable in #346's
store, where `task(id PRIMARY KEY)` is one row per id. His 01:23 ruling asked for
it to become explicit — a symmetric n:n `related`, distinct from one-way
`depends` — so splitting those entries needs somewhere for the relation to live,
or the split destroys the only record of the pairing.

The marker follows the origin marker's `key: **value**` idiom, because a second
idiom for the same shape would be a second thing to learn:

```text
· related: **#251** ·              one id
· related: **#251, #292** ·        several, comma separated
```

**Both entries carry it, and that reciprocity is the contract's whole point.**
In SQLite the pair is stored once under `CHECK (a < b)` and so cannot disagree
with itself. Prose has no such luxury — an entry is read alone, so a reader who
lands on `#250` must learn about `#251` without going looking. Duplication is
therefore mandatory, and the disagreement it invites is exactly what
`lint.check_related_markers` removes: reciprocity is cheap to enforce and
impossible to remember.

It **ERRORs**, unlike the citation check above, because there was no legacy to
grandfather: the live ledger had zero markers when the check was written, so
strictness broke nothing and the first marker written was checked the day it was
written. That sentence is kept in the past tense deliberately — the ledger now
carries **19 reciprocal pairs**, and the reason the rule could be strict from
day one is worth keeping even though the condition that made it easy is gone.
The **six** errors:

- more than one marker on an entry (two claims about one relation is none);
- the wrong case — `Related:` is a claim a reader would have to interpret;
- a value naming no `#N` at all;
- an id that is not in the ledger (a relation pointing at nothing is worse
  than none);
- an entry naming itself;
- **present but unparseable** — the field is there and the bold span is not
  (#395). This one was added last and it is the reason the list is worth
  reading: the check used to `continue` past such an entry, and *skipping* and
  *passing* print the same thing, which is nothing. Three entries had written
  the marker without asterisks and were skipped in silence, hiding four broken
  relations that no run had ever reported. **The error names the shape**, not a
  downstream reciprocity symptom about claims the check never saw, because the
  reciprocity message points away from the cause.

Two shapes that look right and are not, both found by walking into them:
**two adjacent bold spans** (`**#7**, **#8**`) yield only the **first** id, so
the list must live inside **one** span — `**#7, #8**`; and the vocabulary
**cannot be quoted in prose** inside an entry, because the value pattern runs
forward to the next `**` anywhere in that entry and manufactures a phantom
marker. The check anchors the field to line-start or a `·` separator for exactly
that reason. A clean run now prints how many entries it **skipped as
unparseable** alongside the pair count, so the coverage cannot shrink in
silence.

**The marker may hard-wrap**, like `origin:`, because the loop writes at ~72
columns; the check joins each entry's lines before reading it. A bare `#N` in a
body remains a **cross-reference, never a relation** — `blocked on #264` creates
no obligation, or most of history would suddenly owe reciprocal markers.

`depends` is deliberately **not** specified here. Its Markdown form has to
reconcile with the 29 entries that today say `blocked on #N` in prose, and
deciding that — marker or prose — is its own task. A contract written ahead of
its evidence, with nothing using it and 29 entries contradicting it, is worse
than none.

## `.dreamwork/tasks.md` — blocked on a human decision (#419)

He tried to rule on `#264` and found no question to act on. The loop had told
him it was the only thing on his desk while no `questions.md` entry existed for
it, so the loop reported itself blocked on him and gave him nothing to rule on.
His words: *"we should structure things in such a way that it's impossible for
us to be blocked on a user decision without a corresponding question … there
always has to be an answer in our data."*

**The invariant (one half of it is checkable; the other half is refused
below):** every open task whose blocker is a **human decision** has a
`questions.md` entry that is either **open** (awaiting his ruling) or
**answered-but-unfolded** (ruled, awaiting the loop's processing). Both are
legitimate. **Absent is not.** A task cannot be blocked on him with nothing on
the channel to him.

A task cannot currently SAY this. Entries express it in prose — *"awaiting his
ruling"*, *"blocked on #264 Q2"*, *"do not start without his ruling on S1/S2/S4"*
— and prose is not checkable. So this marker exists, and it follows the
`origin:` / `related:` `key: **value**` idiom because a second idiom for the same
shape would be a second thing to learn:

```text
· blocked-on: **human** ·              the blocker is a human decision
```

**One value: `human`.** It names a *kind* of blocker (his decision), not a
specific question — a task-blocker (`blocked on #352`) is a different relation
and stays in prose, which is the gap `depends` (above) is filed to close. A
`gate:` companion names **where the ruling lives**, when the question does not
carry the task's own id:

```text
· blocked-on: **human** · gate: **#263** ·     the ruling rides a neighbour's question
```

`gate:` is optional and defaults to **the entry's own id**. It exists because a
ruling can ride inside another entry's question — `#371` waited on Q2, which
lived inside `#263`'s ask, so an answer there pointed at nothing the loop could
follow back. A check keyed on *"a question with this task's own id"* would read
such an entry as having no question at all, so a blocked-on-human entry whose
ruling lives on a neighbour MUST name that neighbour with `gate:` or the check
cannot find the data. (The `#371` story is subtler than "blocked, then
unblocked" — see the refused Direction 2 below — but the gate mechanism is
exactly what lets an entry point the check at the right channel.)

**Absence means "no claim", never "unblocked".** An entry with no marker is not
asserted to be unblocked; it is simply not making a machine-readable claim about
its blocker. Most of history (137 open entries as of this writing) carries no
marker and is **deliberately left alone** — the marker is forward-only, not a
retrofit, because retrofitting 137 prose judgements into a closed vocabulary is
the kind of bulk edit to durable memory this repo has already paid for once
(`#353`). The honest subset that earns a marker is the one the evidence supports;
the rest stay prose and the check says nothing about them.

`lint.py` (`check_human_blocker`, inside `check_tasks`) enforces **one
direction**:

- **Direction 1 — ERROR — "there always has to be an answer in our data."** An
  open entry carries `blocked-on: **human**`, and **no** `questions.md` entry
  (open or answered) names the gate id (the `gate:` value, or the entry's own id
  if absent). This is the defect he hit: blocked on him, nothing on the channel.
  **Transitive coverage does NOT count.** An entry whose own id has no question
  is Direction 1 ERROR even if a neighbouring task's question covers the same
  decision — because a reader landing on the entry alone cannot find it, which is
  exactly the shape of the #371 trap. Name the neighbour with `gate:` and the
  check follows it there; leave the gate implicit and the entry owes its own
  question. (Consequence for `#353`: it forbids starting without his S1/S2/S4
  ruling and no question names `#353`; an open question about `#264` covers the
  same ground transitively, but transitive does not count, so `#353` would need
  either its own question or an explicit `gate:` to satisfy this check if it
  carried the marker. It carries none today, so the check is silent on it — the
  coordinator decides whether `#353` earns a marker.)

**Direction 2 — "he ruled and nobody processed it" — is deliberately NOT
implemented, and this is a refutation the brief invited, grounded in the brief's
own amendment.** The amendment (`16:23`) retracted the `#371` specimen: a ruling
that *answers* a decision does not *authorise* the work. His *"Q2 yes"* amended
the design while the **implementation** of that answer was a separately-gated
increment, so reading the landed answer as a green light was the very error
`7c5fc82` made and `6ea8f6b` retracted. That generalises: **"answered ≠
authorised."** An answer may amend a design whose build is withheld (#371),
grant a contract while withholding its build (#294, #254's *"design only"*), or
authorise one scope while a larger one stays open. Checking the amendment's other
three specimens confirms none is a defect either — `#254` is a deliberate
partial (design landed, implementation a separate ask), `#367` is in progress,
`#50` is authorised-but-not-started (a backlog item, not a stall). A Direction-2
rule built on *"the gate's question is answered"* therefore rests on a false
equivalence, and the live repo measures the cost directly: the prose form
`blocked on #N` where `#N` is answered fires on **11 open entries, all 11
legitimate** — every one is a task dependency on `#N`'s *work* landing, not on
its question being answered. `#371` itself, the specimen the brief offered, is
among the eleven. A WARN that fires 11 wrong times and 0 right ones is the
hollow-check failure this repo has spent a day learning to distrust, so Direction
2 is refused. Detecting *"ruled but unprocessed"* belongs to a mechanism that
records **authorisation** (an `authorised:` field, or #263's event journal), not
one that infers it from a question's section heading.

The correlation set comes from the **real parser** —
`watch.parse_open_questions` / `watch.parse_answered` for the question titles —
never a second copy, for the reason every other cross-file check in this file
gives: two readers of one fact drift. Every count the check prints is **derived
at runtime**, never a literal: *"N of M open entries marked blocked-on-human all
have a question"*.

## `.dreamwork/tasks.md` — an open entry that declares ITSELF completed (#335)

The section above catches the case where *git* says a task landed. This one
catches the case where **the entry says so about itself** and no commit
exists to notice: `#261`, a P0, sat under `## Open` for a full day carrying
`completed **2026-07-26 16:21**` in its own metadata run. It was closed in
prose, so there was no `close(#261)` commit for `check_landed_still_open` to
find, and it was structurally invisible. `#247` was a second instance,
undetected until this check ran.

**The contract is about POSITION, not vocabulary.** An entry's metadata is
the ` · `-separated chain of short tags immediately following the title —
the run that carries `P1`, `origin:`, `owner:`. A completion marker
(`completed`, `landed`, `merged` near a date or a sha) **inside that run is
a self-declared close**; the same words in the prose body are not, and are
normal. So:

- **Do not put a completion marker in the metadata run of an entry you
  intend to leave open.** If work partly landed, say so in the body and cite
  the sha, exactly as the `#323` contract above requires.
- Where the metadata run ends is defined operationally, because a ` · `
  chain fades into prose rather than ending at a delimiter: the scan walks
  tokens left to right and stops at the first that contains `;` or exceeds
  50 characters. That boundary is a heuristic. It is correct on all real
  entries today, and every failure is a WARN naming the matched phrase, so a
  misjudgement is visible rather than silent — but if it ever needs to be
  exact, the fix is a real title/body separator in the format, not a longer
  regex.

`lint.check_self_completed_open` **WARNs**, never ERRORs — same reasoning as
`#323`: strong evidence worth a look, not a gate. The message names the id
and the matched phrase precisely so a false positive is obvious to whoever
reads it. Missing file, absent `## Open`, or an empty one: silent.

**A naive keyword rule is wrong here and this was measured, not assumed.**
Searching whole open entries for the same vocabulary returns five hits of
which one is real — and each false positive is a *different* legitimate
reason to be open: `#275` (research landed, his ask still pending), `#283`
(one sub-stage of several), `#269` (acute half landed, broader scope
deliberately open), `#281` (a sha cited for a sub-finding). Removing the
position test makes all four fire plus five more. Position is the entire
value of the check; the vocabulary is the cheap part.

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
  that do not matter. (#349 adds the two exceptions, both over lessons.md's
  first sentences only: `dev/lessons_index.py` reads entries to classify
  them by act, and `lint.py` refuses a new first sentence that
  near-duplicates an existing one — neither judges the prose.)
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

## `.dreamwork/posture` — the three-axis posture, overriding run-mode (#445)

`run-mode` is a single word, and `#443` measured that it carries **three
independent decisions in one**: how fast the loop acts (pace), how much it
asks the human (asking), and whether it works through subagents (delegation).
`assisted` is the only value that implies helpers, and it also implies a
pace, so *"lackadaisical but delegating"* is unexpressible — and that was
tonight's actual session, held in conversation rather than the file. His
`#445` ruling ratified **three orthogonal axes: pace × asking × delegation**,
and deferred widening `run-mode`: today's values convert first, controls come
in a later increment, and this file is the vocabulary a control can be built
against. It is the sibling-file shape (no migration).

**Shape** — three lines, one axis per line, optional `#` comments, trailing
newline:

```
pace: hot
asking: inform
delegation: 1
```

**A present file is an explicit override; an ABSENT file is derived from
run-mode** (the conversion, so a loop that has not been restarted behaves
identically). The mapping lives in code (`lint.RUN_MODE_TO_POSTURE` /
`derive_posture`) as the single source — increment 2's runtime must import it
rather than restating:

| run-mode | pace | asking | delegation |
|---|---|---|---|
| `lackadaisical` | `idle` | `ask` | `0` (own / occasional) |
| `hot` | `hot` | `ask` | `0` (own) |
| `assisted` | `hot` | `ask` | `1` (assist) |

**Asking is `ask` (level 1) for all three, grounded in measured behaviour —
not the middle stop picked for symmetry.** Today's loop writes a
`questions.md` entry AND a review artifact for ~every material decision (108
resolutions and 28 artifacts at the time of writing), and his own `#445`
words are *"you do ask me a lot of stuff."* That is level 1 (ask me
everything), not level 2 (inform — where ~10–20% escalate and the rest is
documentation). Deriving `inform` would make the loop stop asking and start
emitting documents instead — the one regression that would cost him
immediately, and it would look like a successful no-op conversion. Asking is
orthogonal to run-mode (run-mode never encoded it; `#445` added it), so the
derived asking is the same for every old value: today's behaviour.

**Pace for `assisted` derives `hot`** because `watch.py` describes BOTH `hot`
and `assisted` as *"continuous work"* (vs `lackadaisical`'s *"idle-
friendly"*) — the pace is genuinely continuous, so this unpacks a bundle that
was always there rather than inventing a decision. It is the one derivation
that carries forward a bundled assumption (the very thing `#443` identified);
the fix is that pace is now **independently settable**, not that the starting
point moves. A human who had `assisted` now sees `pace: hot` and can change
it without touching delegation — which is exactly what they could not do
before.

An unrecognised run-mode value when deriving is prior art from `#290`: it
falls back to run-mode's own default handling, and `check_run_mode` is what
says aloud that the file no longer matches. **The per-tick re-read is load-
bearing** (`#426`): it is the only way an on-disk change reaches a running
loop, and this file inherits the same contract.

**The three axes** — pace and asking are closed sets of named stops; the
delegation axis carries a number whose label is derived for display.

- **`pace`** — how often the loop acts. Three stops: `idle` (idle-friendly,
  no proactive fan-out), `steady` (continuous bounded work), `hot` (urgent /
  continuous). His "3 stops maybe" applied here, and three is the honest
  shape.
- **`asking`** — how much surfaces to the human. **Four** stops, in his own
  dictation at length (`#445`), and the four are kept deliberately:
  `ask` (*ask me everything* — every material choice produces a review and he
  chooses), `inform` (*keep me informed* — ~10–20% escalate, the rest is
  documentation), `near-auto` (*near-automatic* — nothing surfaces, but each
  material choice is still evaluated and written to a journal, ADR-shaped),
  `auto` (*full auto* — never blocked on a reply). `near-auto` and `auto`
  differ observably: one produces a durable artifact per material choice, the
  other does not. Merging them would delete a behaviour he specified; a
  control that reaches only three of four levels is a control defect in a
  later increment, not a reason to drop a level from the vocabulary.
- **`delegation`** — an **average-concurrency target integer**, not a cap
  (his `#445` Q3). `0` means *occasional* — use a subagent only when it is
  necessary or a particularly good choice (average below 0.5 running); it is
  **not forbidden**. `1` means an average between 0.5 and 1.5; `2` and up
  delegates. The number **steers the average and is never a limit or a
  refusal** — a checker that forgot that and gated on the running fleet size
  would be wrong most of the time, because that is what an average means. Two
  subagents may pair on a single worktree (his `#445`), talking via
  `subagent-protocols`.

**What lint enforces, and deliberately does not.** Pace and asking are closed
sets, so an unknown value **ERRORs** — the silent-fallback hazard from
run-mode / watch-tint, stated as an outcome. Delegation carries a *number*:
nonsense (a non-integer, or a negative) **WARNs** — steer, not gate — and
**nothing here ever reads the running fleet size**, because an average is an
average. The clean-bill row carries the count of valid axes so coverage can
never shrink to silence beside a finding (the rule `#380` codified after a
check's OK row disappeared for the thing it was written for). The closed sets
live in `lint.py` as the single source today; increment 2's dashboard controls
must **import** them rather than restating, the way this file imports
`RUN_MODES` from `watch.py` — a second copy of one closed set is a second
thing able to disagree with the control.

**Machine-local / gitignored**, like run-mode: it is operational posture on
this host, not a portable project default. **No `Migration:` trailer** — this
is a new sibling file, not a widening of an existing one, so nothing an
existing install owns must change.

Checked by `lint.py` (`check_posture`), which reads the closed sets from its
own constants (the single source) and derives delegation's display label from
`delegation_posture`.

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
| `short` + `got` | optional, `true` + int | only when FEWER bytes arrived than were promised — a connection dropped mid-body. `got` is how many actually arrived. **Absent otherwise, never `false`/`0`** |

**Exactly one of `req` / `raw`; `why` is present iff `raw` is.**

**`truncated` and `short` are opposite conditions and neither implies the
other** (#371): `truncated` is a cap *this server* applied to a body too
large, `short` is a promise *the client* broke. Before `short` existed,
`bytes` stated the declared length beside a shorter payload with nothing
saying so — and since this file exists so his words can be recovered after a
handler refuses them, a reader could not distinguish a truncated answer from
a genuinely brief one. Recording it does **not** decide what the response
should be; whether the server refuses a short body or keeps a partial
witness marked incomplete is an open question to the human, and the
behaviour is unchanged until he rules.

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
| `agents` | array of objects, each with at least `name` | live subagents; a reader shows the count and the names. Optional per agent: `in_flight` (one line: what it is doing right now — **the one subfield with two readers**, promoted into `watch.py`'s agent glance and republished by `dreamhub.py` in `/hub.json`, so treat it as load-bearing); `owns` (array of strings — the files it holds; `dreamhub.py` renders it as `name (owns)`, and a non-list renders as none); `task_ids` (array of **ints and sub-id strings** — which tasks THIS agent holds, the per-agent half of `current_task_ids` below, and linted the same way: a plain id is an int, a sub-id is a `"392a"` string, and a quoted plain id `"263"` is always wrong — #402b); `kind` (`utility` when it is not a dreamer); and `awaiting_result` when it was dispatched and has not reported — a dispatched-but-silent agent is otherwise legible only from the coordinator's memory, which is exactly how two deliverables were lost (#144). **This list is a menu, not a whitelist** (#310): `watch.py` folds every agent key it does not name into "the rest" on purpose — *"Whatever is LEFT, not a second known list"* — so an unlisted field is still shown, and nothing here is safe to prune on the grounds that no reader names it |
| `current_task_ids` | array of **ints and sub-id strings** | the task ids this names (#332, #402b). `task` above says what the loop is doing in a sentence; this says *which rows* it is doing it to, and prose is not a substitute because one sentence routinely names several ids in different states ("folding #281's answer, #326 next"). `/tasks` (#281) badges a row "in progress" from this, so a quoted `"#281"` or `"281"` is worse than an absent field: it looks right, lints past the type table, and matches no row at all — silently. **The id vocabulary** (#402b, mirroring the hand-off grammar at `#401`): a **plain** id is an integer (`263`), a **sub-id** is a string of digits then one letter (`"392a"`), and a **quoted plain** id (`"263"`) is always wrong. A live set legitimately holds int and str at once — a lane may be `#392a`, and `status_sync` derives this field from that `task` value, keeping the string form by design (`#402a`). `lint.py`'s `check_status_task_ids` ERRORs on anything that is neither a plain int nor a sub-id string — bools included |
| `dreamers` | array of objects | **one entry per dispatched lane**, reaped by `status_sync` — see the dedicated section below (#402a) |
| `queue` | object, integer `in_progress` and `pending` | queue depth |
| `awaiting_human` | array of strings | **non-empty means the human is the bottleneck.** The one field a reader must never bury (#130, #141) |
| `last_tick`, `last_commit` | string | freshness; a stale `last_tick` is how a stalled loop is spotted |
| `deploy`, `monitors`, `coordinator_next` | strings / arrays | recovery notes for whoever picks the loop up after a compaction |
| `push` | object: `at`, `channel`, `ok`, `detail` | **the loop's push-channel health** (#190). The loop writes one on every attempt, success or failure. `at` is ISO8601 with offset, from the system clock (never memory — the page renders it as an age); `channel` names what carried the push (`attn`, `PushNotification`, …); `ok` is a strict bool the renderer branches on; `detail` is the short reason a human acts on (the 403, the credit message). **Three states are distinguishable from the data:** no `push` key (never tried), `ok:true` (last landed), `ok:false` (last failed) — and only the last earns pixels. `ok:false` is a truthful runtime claim, not a broken file, so it lints clean; only a wrong TYPE is an error. Subfields are a menu like the top level (#310): the loop may grow the object, and nothing here rejects an unlisted key |

The file is **gitignored ephemera** and stays that way. It describes a
running process, so a committed one would be a lie the moment it landed;
that is also why there is no history to compute stats from (#142).

**Two of those fields restate what `tasks.md` already knows, and they had
drifted (#362).** `queue` restates open-entry depth; `current_task_ids`
restates what is in flight. On 2026-07-28 both were wrong at once — `queue`
summed to 115 against 123 open entries, and `current_task_ids` was `[]`
while three agents named their `task_ids` — because nothing compared either
pair. Eight tasks of drift accumulated across one night of hand-maintained
edits. That is the failure `lessons.md` (#306) tells you to assume: where
two files hold two halves of one fact, they have already drifted.

So `lint.check_status_agrees_with_ledger` **WARNs** when `queue` does not sum
to `parse_ledger`'s open count, and when `current_task_ids` is empty while
`agents[].task_ids` is not. WARN and not ERROR is the load-bearing choice:
this file is a best-effort projection the loop is explicitly told must never
block a tick, so a momentary lag mid-increment is *truthful* and crying red
on it would punish exactly the honesty the file exists to provide. Drift
nobody measures is the thing that is not truthful.

It is silent on an absent field (absent means "not adopted", as everywhere
here), silent when `agents` is absent or empty, and silent when a `queue`
value is not an integer — that last one belongs to `check_status`, and
comparing a *partial* sum to the full ledger would report a confident wrong
gap on a file whose real fault someone else is already naming.

## `.dreamwork/status.json` — the `dreamers` array (#402a)

One entry per dispatched lane. The coordinator writes an entry at dispatch
time (the lane's task, its dispatch pid, the brief path); `status_sync.py`
reads the array every run and reaps entries that no longer own files. **A
stale entry says a free file is owned**, so the coordinator declines a
dispatch it could have made — `#264` measured file contention as the binding
constraint on how much runs at once, and stale ownership manufactures that
constraint from nothing. That is why the array is reaped, not just written.

**Entry shape:**

```json
{"task": 263, "pid": 1970752, "brief": "/abs/path/to/brief.md"}
```

| Field | Type | Means |
|---|---|---|
| `task` | **int (plain) or str (sub-id)** | the task this lane is working. Mirrors `current_task_ids`' id vocabulary (#402b): a **plain** id is an int (`263`), a **sub-id** is a string of digits then one letter (`"392a"`). A quoted plain id (`"263"`) is always wrong — `status_sync` normalises it to int on write, so a bad value read in does not survive. **Tolerate on read, normalise on write**: the file has more than one writer (the coordinator at dispatch, the syncer at reap), so the syncer accepts either type on read and writes back the canonical form. |
| `pid` | int | the lane's dispatch process. **The pid is exact** (`kill -0`); a dead pid means a dead lane and the entry is reaped. A lane whose recorded pid is gone but whose argv still names the brief is a live lane whose wrapper exited, and the brief path is the order-independent fallback. |
| `brief` | string | the absolute path to the lane's brief, used as the fallback liveness signal when no pid is recorded (order-independent: the brief is found *wherever* it appears in argv, so a flag between binary and alias does not hide it). |

**An entry is reaped when EITHER signal says "not an owner":**

1. **Its pid is dead** — `kill -0` returns "no such process". The lane's
   process is gone, so it owns nothing. This is the case `live_lanes`
   already handled before #402a landed.
2. **Its task is no longer under `## Open`** — the coordinator moved the
   task to `## Recently landed`, so the work finished and the lane no
   longer owns files. **This is the half #402a added:** previously a
   landed task with a live pid was a hard STOP (return 2, *"a lane is
   working on a task the ledger calls closed"*), which blocked the whole
   sync for one stale entry. Now it is reaped and the sync continues.

Open-ness is asked of the **live system, not memory**:
`status_sync.open_ids` reads the ledger's `## Open` section through the
shared `watch.IDS_ONLY_SPAN` pattern (the one-copy head form, #331) —
never a hand-rolled parser, and never a bare `text.split('## Recently
landed')`, which also appears in an entry's *prose* and has corrupted the
file twice. A sub-id (`392a`) compares against its base id (`392`).

**Never crash on a malformed entry.** A syncer that exits 1 stops
protecting everything after it. Entries that are not a dict, carry no
`task`, or hold neither a parseable pid nor a brief are **skipped and
reported on stderr** (`skipped N malformed dreamer entr…`), and the sync
continues for the survivors. A junk entry never reaches `live_lanes`.

**Read the file itself defensively.** `status.json` is gitignored ephemera
written by more than one hand (the coordinator at dispatch, the syncer at
reap, the dashboard on tick), so a file that is absent, empty, truncated
mid-write, or a non-object JSON value is the NORMAL case, not an exception
— the brief's own words: *"a check that hard-fails on it is worse than
none"*. `status_sync._read_status` therefore neither crashes on such a file
(an uncaught `JSONDecodeError`/`AttributeError` stops protecting everything
after it) nor overwrites it with freshly derived fields (that would destroy
the author-written `deployed` / `task` / `monitors` / `owed_verifications`
the broken file could not yield). It reports the reason on stderr, leaves
the bytes untouched, and returns a distinct refusal; the coordinator
rebuilds from the durable sources — the ledger and `submissions.log` —
never from a projection. This is the file-level half of "never crash"; the
entry-level half is the paragraph above.

**Nothing else about a survivor changes** — the entry is kept verbatim
apart from task-id normalisation, so ownership, agent, and any other field
the coordinator wrote are preserved.

`status_sync.py` is the sole reaper; the coordinator is the sole writer at
dispatch. `lint.py` does not check the array's contents (it is gitignored
ephemera describing a running process), so the contract is enforced by the
reaper itself plus the id-vocabulary check on `current_task_ids`.

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

## `.dreamwork/review/src/<slug>.html` — the review artifact's source (#325)

Every request for a review ships a self-contained artifact, so that page is
the surface the loop's proposals are read on. Twelve hand-authored ones
carried **five distinct `font-family` declarations** and eight page
backgrounds all meaning "the dark one". `tasks-page.html` is the one he
named as good, so its stylesheet is now a template and artifacts are
**built**, not hand-rolled:

    python3 <skill-dir>/review_artifact.py build .dreamwork/review/src/<slug>.html

Template: `review-artifact.template.html` in this skill's directory, so it
ships with the bundle and is reachable from whatever project the loop runs
on. Builder: `review_artifact.py` beside it. It writes
`.dreamwork/review/<slug>.html` — the source's own directory matters,
because `watch.py`'s `list_reviews` is a non-recursive `os.listdir`
filtered on `.html`, so a source **in `src/`** is invisible to it while one
sitting beside the artifacts would be listed and served to him as a
half-built page. The builder refuses a source anywhere else.

The source is one file: a header comment of `key: value` scalars, then
named blocks.

```html
<!--dreamwork-review-source
title: #325 · The review artifact becomes a template · proposal
identity: review artifact · template
context: task #325 · one template, one builder, one stamp
status: awaiting review
headline: Twelve pages, five font stacks, one template.
tag: proposal only
sub: task #325 · 27 July 2026 · self-contained proposal
skip: Skip to the decisions
skip_href: #decision
-->
<!--#lead-->
<p class="lead">The paragraph the reader starts on.</p>
<!--#body-->
<section aria-labelledby="crux-t">
  <div class="label" id="crux-t">The crux</div>
  <p class="read">…</p>
</section>
<!--#footer-->
Prepared for task #325 · 27 July 2026 · offline-clean, no external requests.
```

- **Header.** Starts at byte 0 with `<!--dreamwork-review-source`, one
  `key: value` per line, closed by `-->`. Values are single-line HTML
  fragments (inline `<code>` is fine and is used constantly).
- **Blocks.** `<!--#name-->` alone on a line opens a block that runs to the
  next marker or to end of file. Content before the first marker is an
  error, because it would otherwise vanish.
- **Required:** `title identity headline lead body footer`. **Optional:**
  `context status tag sub call aside nav skip skip_href aside_label` —
  either as a header scalar or as a block, whichever suits the length.
- **Fail loud in both directions.** A missing required slot is an error and
  so is an unknown key: the failure mode of every template system is a typo
  that silently drops a section, and an artifact missing its own
  recommendation still looks finished. `skip` without `skip_href` is an
  error too.
- **A component's children carry that component's classes, or the build is
  REFUSED** (#347-adjacent). The template styles `.fact .number` and
  `.fact .caption` and nothing else, so `<div class="fact"><strong>122</strong>
  <small>open ids</small></div>` renders as `122open ids` — the number running
  straight into its caption — with no other symptom at all. `build` exited 0 and
  `check` reported `current` while it was wrong, twice, in tonight's own
  decision artifact. Bare text directly inside a component is the same defect.
  Nesting inside a documented child (a `<code>` in a caption) is **not**, which
  is why the scan parses HTML rather than matching patterns: depth is the whole
  distinction, and a rule that forbade `<code>` in a caption is a rule someone
  deletes. The vocabulary lives in `review_artifact.COMPONENT_CHILDREN`, which
  has one entry on purpose — the template documents about twenty components, and
  rules for the rest would be guessing at usage nobody has measured, which is
  the very complaint this check exists to answer.
- **A grid row short of a full last row WARNs and still builds.** A `.facts`
  row wants a multiple of the column count, and a three-item row in a
  four-column grid renders with one visibly empty track. Advisory rather than
  fatal for two measured reasons: it is legal markup, and a fatal rule would
  make `note-reply-threading-254.html` — an existing source, with a legitimate
  three-fact row — unbuildable. That was found by injection, not argued: making
  the rule fatal reddened the live-source sweep. **The column count is read
  from the template's own stylesheet**, widest `repeat(N, …)` across media
  queries, never written into the checker: a literal `4` is a check with an
  invisible expiry date the first time the grid is reshaped.
- **Both run in `build`, against the built output, and `check` is untouched.**
  `check` answers exactly one question — which template did this come from —
  and its non-zero exit means `stale`. Widening it would make it fail on the
  untemplated artifacts #325 deliberately chose not to migrate.
- **Optional means gone, not empty.** An unset slot deletes its whole
  region, `status:` with nothing after it counts as unset, and an aside-less
  hero drops to `hero-grid solo` rather than holding a 240px column open.
- `TEMPLATE_STAMP` and `hero_solo` are **derived**; a source that sets one
  is an error rather than being quietly overridden.

**The stamp is how iteration stays honest.** Each build writes
`v<series>+<8 hex of the template file>` into a `<meta
name="dreamwork-review-template">` and into the footer, computed from the
template's bytes — nothing has to remember to bump it. So after the
template changes, every artifact built before it says so:

    python3 <skill-dir>/review_artifact.py check .dreamwork/review/*.html
      current     …/#325-template.html
      stale       …/older.html  (built from v1+0f3a11c9)
      untemplated …/tasks-page.html

`untemplated` is the third answer on purpose: the twelve artifacts that
predate this are **not migrated**, and a check with only pass/fail would
have to lie about one of them.

**Checked two ways now (#329).** `lint.py` (`check_review_artifacts`) runs
`review_artifact.py check` over a target's `.dreamwork/review/*.html` and
**WARNs on `stale`** — so once the template improves, every artifact built
before it warns until it is rebuilt, which is the drift #325 exists to end, no
longer returning by a different door. It stays **silent on `untemplated`**: the
twelve artifacts that predate the template are not migrated, and a WARN on each
of them every run is noise everyone learns to ignore. Absent `.dreamwork/review/`,
no `.html` in it, or `review_artifact.py` missing/unrunnable all degrade
silently — "cannot check" must not read as "nothing to fix", the same rule
`check_landed_still_open` follows for a non-repo target.

The source and template fidelity — every shared CSS selector held to identical
declarations, palette compared token by token, both parsed at runtime, and that
a build fetches nothing — stays checked by `test_review_artifact.py`, because
those are properties of *this skill's* files rather than a target's. Divergence
from the reference is possible but never silent: it costs one named entry in
`TEMPLATE_ONLY`, `DECLARATION_DIVERGENCES` or `TOKEN_DIVERGENCES` there.

## `.dreamwork/review/src/<slug>.html` — essential marks (#367)

His idea, and his analogy decides the design: *"those little thin postits that
lawyers use to indicate key points and where you need to sign."* A lawyer's flag
marks **where you must act**; it is not a table of contents. So marks are a
different axis from `nav`, which is structure — conflating them produces a second
table of contents, which is not what he asked for.

**Written before the implementation, deliberately**, because the builder and the
guard both read this and a shape invented twice is a shape that drifts.

**The word "mark" is already taken in this file's own vocabulary** and the
collision is worth naming before it costs someone an hour: `parse_source` calls
its `<!--#name-->` **block markers** "marks" in the code. Those are unrelated.
This section is about *essential marks* — flagged passages — and the source
syntax below deliberately does not reuse the `<!--#…-->` form.

**Source form.** A mark is declared **on the block it flags**, not in a separate
list, so it cannot drift from the passage it points at:

```html
<section aria-labelledby="crux-t" data-mark="the cliff">
```

- **`data-mark="<label>"`** on a **block** element inside `body`. The label is what the
  tab reads, and the element must be a block container: the flag anchors with
  `left:calc(var(--measure) + .4ch)` against its own box (the marked element,
  made `position:relative`), so for a block — whose box starts at the reading
  column's left edge — it lands at the column's right edge. For an **inline**
  element the containing block is the inline box, so `left` resolves from that
  box's offset and the flag drifts right and clips past the page edge (measured
  on a two-marks-one-line probe: clipped by 151px at the 861px cliff, and the
  flag does not reflow so the clipping grows as the viewport shrinks). The
  builder cannot compute layout, so the gate is the **tag**, not a computed
  style: a `MARKS_BLOCK_HOSTS` allowlist (`p`, `li`, `section`, `div`,
  `h1`–`h6`, `blockquote`, `td`, `figure`, …) in `review_artifact.py`. An
  allowlist rather than an inline denylist on purpose — an unknown tag
  **refuses** (fails closed) instead of silently clipping, where a denylist of
  `span`/`em`/… would fail open on `abbr`, `kbd`, `mark`, `sub` and whatever
  ships next. `data-mark` on a `<span>`, `<em>`, `<a>`, `<code>` or any other
  inline tag is **refused at build time**, with the offending element and its
  label named (a loud build error is the point — a clipped flag is silent).
  Closed by #396.
- **Document order is mark order.** There is no explicit index, because an index
  is a second thing to keep in sync and the reading order is the order he wants
  to walk them in.
- **A mark on an element with no stable id is an error** — next/prev must be able
  to land on it, so the builder assigns nothing implicitly and refuses instead.
  **The `id` must be on the SAME element that carries the `data-mark`**, not on an
  ancestor. `<section id="x"><p data-mark="y">` is refused, and that is correct
  rather than pedantic: the flag points at a height on the page, and the element at
  that height is the marked one — a parent id scrolls somewhere else. Increment 1's
  builder already enforces this (the #367 lane found it by writing fixtures the
  other way and having every one refused), and increments that render the tab and
  next/prev must key off the marked element's own id. So the body a renderer
  receives has every mark individually addressable, by construction.
- **A label must carry readable text.** `data-mark` with **no value** (the boolean
  attribute form) is **not a mark** and is ignored — the contract defines a mark by
  its label, and a valueless flag has nothing for a tab to read. `data-mark=""` and
  a whitespace-only label are **authoring mistakes and are refused**, because they
  do reach the renderer and produce a tab with nothing in it — a blank postit that
  reads as a rendering bug and is not one.
  **Closed by #389** (`b79f339`, `e0a3356`): the valueless form is ignored, `""` and
  whitespace-only are refused with the offending element named, and all three are tested.
  **Closed for zero-width too by #367 increment 2a:** the refusal is no longer
  `str.strip()`-based — it is "no character outside Unicode categories `Z*` and `C*`",
  so it catches every `Zs` space (U+00A0, U+2003, U+3000) AND `Cf`/`Cc` (U+200B
  zero-width space, control chars) that `.strip()` did not see. A label of only
  zero-width spaces would render a blank tab, which matters more once tabs are
  rendered. The **valueless** `data-mark` is still ignored: the `label is None`
  carve-out sits before the readable-text check, so widening `.strip()` to the
  category rule cannot swallow it (the two #389 guards — `valueless` and the
  id-less valueless element — are what hold that discrimination).

**The count, per his ruling of 2026-07-28 05:35** — he overrode the loop's
proposal of five-and-refuse:

- **Soft cap 7:** the builder **warns** at 8 or more, through the existing `warn`
  advisory channel (the one that reports "documented component" findings), not by
  refusing.
- **Hard cap 15:** the builder **refuses**. Fifteen flags is wallpaper, and his
  whole point was that five help and fifty do not.
- The band between them is deliberate: a refusal at the number where his judgement
  and the loop's differ makes the tool argue with him.

**The label, per the same ruling** — he overrode a ~12-character cap with builder
truncation:

- **Up to ~6 words**, rendered as a **two-line tab at a smaller text size**. The
  tab grows to fit the label; **nobody truncates.**
- **A measurement is owed before this is built**, and it is the same class of thing
  that already refuted three designs for this feature: a two-line tab is taller and
  possibly wider than the tab the geometry was measured against, and the gutter
  outside `.wrap` is **16px at every viewport from 1120px down**. Measure ~6 words
  at two lines against that gutter. **If it does not fit somewhere, report the
  measurement** — do not quietly reintroduce the cap he just removed.

**The safety property that makes this shippable.** All the existing artifacts
declare no marks. So:

> **A source that declares no `data-mark` renders no rail, tab or control, and
> its body is byte-identical to the pre-change builder's.**

Increment 1 held the stronger whole-document byte-identity ("differs from
today's only in `TEMPLATE_STAMP`") and it was the right net while the frame
gained only inert machinery. Increment 2a — which adds the rail's CSS to the
template — **retires it deliberately**: a no-marks artifact legitimately gains
`<style>` rules it does not use, so a whole-document digest can no longer hold
(and the two obvious fixes — deleting the check, or re-capturing the digest —
are both wrong; the first opens the frame to drift, the second breaks the
companion that re-runs the pre-change builder out of git). The check is replaced
by the true property above: no mark chrome in the output, and the BODY
byte-identical to the pre-change builder's (cross-checked against it out of
git). The frame's CSS is held to `tasks-page.html` by the fidelity tests and
staleness by the stamp tests, so nothing the retired check stopped catching was
unguarded.

## `.dreamwork/docs/research/src/<slug>.html` — a research artifact's source (#484)

Research HTML is built through the **same one builder and the same source
format** as the review artifact above — a second template pipeline would be
the five-font-families drift with a new name. The layout is the same trick
one directory down: sources in `.dreamwork/docs/research/src/`, built to
`.dreamwork/docs/research/<slug>.html` by

    python3 <skill-dir>/review_artifact.py build .dreamwork/docs/research/src/<slug>.html

`build_path` is generic (any `src/<slug>.html` builds beside its `src/`), so
no builder change was needed. The differences from a review artifact are all
in the lifecycle, not the format: a research source declares `no_ask:` and
`no_if_silent:` (it parks no decision — it is a record), it is listed by
`/research` rather than the reviews panel, and it is **kept while its
conclusion holds** rather than archived when a question is answered
(`.dreamwork/docs/research/README.md` is the contract). The serving half is
the `/reviewraw` idiom as `/researchraw`: bare `.html` basenames only, so a
`src/` source can never be served as a finished page.

## Migration notice — a hot-path banner in a data file (#458)

A migration that changes the *meaning* of a data file a long-running agent
still re-reads leaves a **notice in that file**. Migrations apply at orient
only; a loop that never re-initializes never sees `migrations/`. Its skill
files are cold; the data file is hot. The notice is the channel.

Design: `.dreamwork/docs/plans/migration-notices.md`. Writer:
`migration_notice.py` beside this skill's other tools.

```html
<!--dreamwork-migration-notice
migration: 2026-07-29-01-task-store.md
file: .dreamwork/tasks.md
summary: this ledger is an archived copy; live store is SQLite — read the migration and update your routine
-->
```

- **Placement.** At **byte 0** of the host file (the file whose meaning
  changed — often `.dreamwork/tasks.md`). One block. A write **replaces** any
  existing well-formed notice first (the shrink rule: the Nth migration leaves
  one banner, not N).
- **Open marker.** A line that is exactly `<!--dreamwork-migration-notice`
  (optional trailing whitespace). Same family as `<!--dreamwork-review-source`.
  A prose mention of the string mid-line is not a notice.
- **Fields.** `key: value`, one per line, single-line values only.
  - **`migration`** (required): a `migrations/` filename matching
    `YYYY-MM-DD[-NN]-slug.md`. A pointer, not a copy of the instructions —
    when the migration's "How to apply" changes, the notice does not need a
    rewrite.
  - **`file`** (optional): the host path the notice is about.
  - **`summary`** (optional): one human-readable line. Must **not** look like
    a ledger entry head (`- **#N…`); the writer refuses such a value because
    `lint.LEDGER_ID` / `watch.LEDGER_ENTRY` match `^- \*\*#` with `re.M` over
    the whole file and a smuggled head would invent a phantom id.
  - Unknown keys are an error at parse time (fail closed on typos).
- **Close.** A line that is exactly `-->`.
- **Trust.** Only a migration writes these. An agent treats a notice as a
  protocol signal from its own repo, never as peer authority.
- **Retirement.** A notice is **spent** when `.dreamwork/skill-version` is
  lexicographically `>=` its `migration` field (the same order
  `migrations/README.md` uses for versions). `migration_notice.py retire`
  removes a spent notice. Orient should retire after bumping skill-version;
  a still-running agent that self-updates after reading the notice may retire
  it the same way.
- **Indifference of the ledger readers.** A well-formed notice is not a
  `- **#N**` line, so `watch.parse_ledger` and `lint.LEDGER_ID` / `check_tasks`
  see exactly the same entries with or without it. That property is tested in
  `test_migration_notice.py` by deriving both sides from the production
  readers — never from a hand-written expected id list.

```
python3 <skill-dir>/migration_notice.py write  --path <file> --migration <name.md> [--summary TEXT]
python3 <skill-dir>/migration_notice.py retire --path <file> --skill-version-file .dreamwork/skill-version
python3 <skill-dir>/migration_notice.py parse  --path <file>
```

## `.dreamwork/docs/briefs/*.md` — a worktree brief declares its owned paths (#465)

A lane dispatched into a worktree (``.worktrees/<name>`` on ``wt/<name>``) can
edit the **main checkout** instead of its worktree, and nothing notices until a
merge fails — or worse, a coordinator commit sweeps the lane's half-finished
edits into a ledger commit under the wrong message (``12f47e3``). The
invariant the whole fan-out rests on — *parallel increments only ever touch
disjoint files* — is void the moment a lane writes outside its worktree, and a
brief cannot enforce it (the incident's brief named the worktree twice and was
ignored). Only a check can.

**A worktree-naming brief declares what files the lane owns**, so the
lane-containment guard (``dev/lane_guard.py``) has a non-empty ownership set
to protect. The line follows the ``origin:`` / ``related:`` ``key: value``
idiom:

```text
Lane-owns: watch.py, dev/capture/, test_watch.py
```

- **Comma-separated repo-relative paths.** A path ending ``/`` owns the whole
  directory (prefix match); a bare path owns exactly that file.
- **One or more ``Lane-owns:`` lines** — repeatable, unioned. The guard
  normalises backslashes and strips backticks, so `` `watch.py` `` and
  ``watch.py`` are the same.
- **The brief the lane was actually given is the source.** Not ``status.json``
  (whose ``dreamers`` entry carries ``{task, pid, brief}`` and **no file
  ownership and no worktree path** — the brief's premise that it did was the
  drift the "assert the precondition at runtime" rule exists to catch), not a
  second registry. The brief is committed under ``.dreamwork/docs/briefs/`` and
  already carries a prose "Yours: …" list; this makes that list
  machine-parseable.

`lint.check_brief_lane_owns` **ERRORs** when a brief that names a worktree
(``.worktrees/``) declares no ``Lane-owns:`` paths — so the omission is loud at
brief-write time rather than a silent no-op at commit time. A guard over an
empty ownership set protects nothing, and the check refuses to let that state
stand. History before the rule landed in SKILL.md is grandfathered by commit
time (content-resolved cutoff, never a pinned sha — a hollow no-cutoff is an
ERROR, not a silent pass).

**The guard is machine-local** (``core.hooksPath`` is not committed), so the
*script* is committed and *enabling* is a documented step:
``python3 dev/lane_guard.py --install`` chains into the pre-commit hook on the
main checkout only (it exits 0 in linked worktrees, so lanes commit freely).
The committed artefacts that protect every checkout regardless of enablement
are this brief convention (enforced by ``lint``) and the pre-merge backstop
``lint.check_lane_containment_backstop`` (#468), which needs no hook at all.

**The backstop reads the same declaration one step earlier.** It ERRORs when a
path a live lane owns is **dirty** in the main checkout — staged, unstaged or
untracked — which is the state that actually did the damage: the `#263` merge
aborted on dirty files before any commit was attempted, so the pre-commit guard
would never have fired. Lanes come from git's own worktree registry (a linked
worktree on a ``wt/*`` branch), never from ``status.json``.

**It degrades to silence, never to an accusation**, in each of the four ways it
can be unknowable: git unavailable, no linked lane worktrees, git status
unreadable, or a lane whose brief declares nothing. The last is the subtle one —
an undeclared lane is *not counted as examined*, because a clean bill that
included it would claim coverage the check does not have. And the clean-bill row
is suppressed whenever a finding exists in the same run: a check that prints
"no owned path is dirty" beside an error naming one gets read as noise and then
ignored. Both of those were found by red-proofing the check itself.

**The merge-time gate is an explicit assertion, not a hook** (#468 R2). The
backstop is ambient — it fires when `lint` runs — but a lane's stray edit can
land in the main checkout between two lint runs and live right up to the
``git merge`` that aborts on it. R2 is the assertion run in front of that merge:

```
python3 dev/lane_guard.py pre-merge wt/<lane>
```

It is a **subcommand, not a ``pre-merge-commit`` hook**, for two reasons measured
against this harness: a ``pre-merge-commit`` hook does not fire on a
**fast-forward** (the common merge of a lane branch whose base is current HEAD),
and installing a hook is a separate consent ask whose own half (#465) is still
un-granted. The honest weakness of a subcommand is that it must be remembered —
the merge is run with the assertion in front of it, not automatically — and the
ambient backstop is what covers the lane-owned-dirty case whether R2 is run or
not. R2 adds the dimensions the backstop cannot reach: the coordinator's **own**
uncommitted tracked work (no lane owns it, so the backstop is silent, yet a merge
aborts on it) and an untracked file the merge would **clobber**.

It refuses (exit 1) with the **reason and one action**, never a destructive
command — it stashes, resets and checks out nothing: a lane's edit in the main
tree names the lane/path and ``git worktree remove <path>``; the coordinator's
own work says "commit or unwind"; a clobber says "would be overwritten by merge".
It declines (exit 2) when it cannot evaluate — not the main checkout, ``git
status`` unreadable, or a branch that does not resolve — rather than asserting a
clean tree it never measured. And it **reuses the reader**: ``lint.lane_owned_paths``
is the single lane-ownership definition, so the backstop and the pre-merge
assertion share one reader — two callers, one place the parsing can drift, not
two.

## `/summary.json` — a whitelist view, not a projection of everything (#275 Q5)

`watch.py` serves `/summary.json` as a **whitelisted** view of `collect()`,
behind the same `_preflight()` GET authority gate as every other route. Output
keys: `generated`, `open_questions`, `questions_health`, `answers_health`,
`tint`, `run_mode`, `posture` (`pace`/`asking`/`delegation`/`source`),
`skill_identity` (`commit`/`skill_version`), `burndown_counts`
(`open`/`arrived`/`landed`), `skill_version`.

Redaction is a **whitelist**, held as `SUMMARY_ALLOWED` / `SUMMARY_DENIED` in
`watch.py`, and the partition is what makes it safe to extend: a **new
`collect()` key is refused until it is classified into exactly one of the two
sets**, enforced by `TestSummary.test_summary_classifies_every_collect_key`. A
denylist would leak by default the moment `collect()` grew a field — this fails
loudly instead. One key is deliberately in both roles: `files` is allowed as a
*source* and denied as *output*, projected down to the `skill_version` scalar.
Guard: `dev/capture/summaryjson.mjs`.

## Review artifact references in a question body (#472)

Prefer a **backticked path**: `` `.dreamwork/review/<name>.html` ``. The
dashboard turns that into a dock link on `/review?p=<name>` carrying the
question. Do **not** write a markdown inline link to a relative `../review/`
path — `mdSpans` does not general-linkify, so it did not render as a link at
all, and the relative form is *also* wrong for the `/questions` route, so even
a rendered one would 404. Both halves were the same reported bug. A markdown
link whose target is already a review basename under `.dreamwork/review/` or
`../review/` is now rewritten to the same dock by `linkifyReview` and is
tolerated, but **new asks use the backticked form** so the corpus stays one
shape — the corpus majority (`#294`, `#445`, the fixture) already does.

## `.dreamwork/question-sigs.json` — when an entry last changed (#473)

Machine-local and gitignored, like `run-mode` and `watch-events.log`, because it
describes what *this* dashboard has seen. One record per question entry: a
content digest over title + body + follows + answers, and `updated_at`. First
sight stores the digest with `updated_at` null; a later digest change stamps the
clock and emits one `question-updated via watch: <title>` line to
`watch-events.log`.

The definition is **per-entry content**, and the three alternatives were
rejected for reasons worth keeping: **file mtime** moves when a *neighbour*
entry is answered, since every entry lives in one file; **git history of
`questions.md`** needs the file committed, and the coordinator commits minutes
after writing, so it lags and is partial; a **format marker in `questions.md`**
would change the parsed ledger — a migration nobody asked for. The display half
is the reliable deliverable; the event half rides `watch-events.log`, which is
**best-effort and lossy by design** (`log_event` swallows `OSError`), so it is
a convenience and never a notification to rely on.

## Guard run-log verdict contract — registration is not execution (#471)

Every guard in `dev/capture/` (whether it imports `report.mjs` or inlines the
idiom) writes verdicts to stdout as one line per assertion, `PASS <name>` or
`FAIL <name>`, separated from coverage and notes by a line containing only
`----`. A guard that exits before its first assertion emits the crash sentinel
`FAIL the guard threw before finishing its checks` as its only FAIL-ish line;
that marks **did-not-judge**, not a verdict.

The `guards` recipe captures each guard's combined stdout+stderr to
`<OUT>/<guard>.log`. `lint.py guard-execution <OUT> <guard>…` classifies each
log: a guard **ran and judged** iff its log carries at least one `^(PASS|FAIL) `
line that is not the sentinel. The recipe fails the run when any requested guard
did not run and judge, and the OK row carries **both** numbers —
`guards: <executed> of <registered> registered guard(s) ran and judged` — because
the row that hid `#471` for three and a half hours carried one. A
zero-assertion guard is not-executed by construction. This is the detector for
`#310`'s family: a guard can be registered, have a file, be believed to gate,
and never run.

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
