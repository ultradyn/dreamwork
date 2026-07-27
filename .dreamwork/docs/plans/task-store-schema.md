# Task store — entity schema and read-only CLI (the half #263 does not gate)

**Tasks:** #346 (split from #294), read requirements from #281 and #289
**Status:** design; no implementation authority. No table is created and no CLI
ships under this id.
**Date:** 2026-07-28

## Why this exists separately

His `do-next` steer (watch 2026-07-27 23:33) was *"I think we need to start
working on the sqlite db and cli next. it feels like it's becoming a blocker."*
#294 is gated on #264, which is gated on #263 — and #263's gate is not a missing
design. `user-event-journal.md:4` states its own status as *"human approval
required; no implementation authority"*, and its approval gate authorises *"a
separate red-first implementation plan"*. So the event model is designed,
reviewed and PASS; it is **unratified**.

The gated question is #264's: *"decide whether it shares #263's journal or uses
a task-state outbox, but never dual-write two fallible truths."* That is a
question about how a **transition** becomes durable. The columns describing a
task **at rest** do not vary with the answer — a journal-sourced materialised
view and an outbox-sourced table expose the same entity. This document is
therefore the entity and its read surface, and nothing else.

**Explicitly out of scope, and gated:** every write verb, `grab`, claims,
leases, CAS, the transition history table, the burndown projection, the
dashboard outbox, and cutover itself. Also out: creating the schema. A schema
that exists before #263 is ratified is the double migration he has warned about
twice.

**In scope:** the entity schema, the read-only CLI verbs over it, and the
migration script's *parse and report* half — the part that reads today's
Markdown and tells him exactly what is in it, which is useful on its own and is
how the schema gets falsified before anything depends on it.

## What the live ledger actually contains

Measured 2026-07-28 00:40 against `.dreamwork/tasks.md` (111 open ids, 126
landed) using `watch.ledger_entries` and `watch.parse_ledger` — the readers the
system already uses, not a fresh regex. **A fresh regex was tried first and was
wrong**: `text.index('## Open')` matched a prose mention of the heading in the
file's preamble and reported 10 open entries instead of 111. That is the third
time tonight a hand-rolled scan of this file has produced a confident wrong
number, so every count below comes from the real reader over line-matched
headings.

Five findings, each of which breaks an obvious schema:

**1. An entry is not a task id — three entries carry two ids each.**
`- **#138/#156**`, `- **#250/#251**`, `- **#292/#293**`: one body, two
permanent ids. `CREATE TABLE task(id INTEGER PRIMARY KEY, body TEXT)` must then
either duplicate the body under both ids — two rows that can disagree about a
task the ledger deliberately states once — or drop an id, and ids are permanent
and never reused.

**2. And the count that would catch that agrees by accident today.** Open
entries = 111 and open ids = 111 *right now*, because all three combined
entries happen to be under `## Recently landed`. A check pinning those equal
would pass today, pass its own red-proof, and start lying the day a combined
entry is opened. This is the documented "two numbers that had to differ met"
failure, visible in advance for once: **derive both counts and assert the
relationship you mean, not their equality.**

**3. Priority bands are not a closed set.** `P2`×88, `P3`×35, `P1`×30, `P0`×2,
and the compounds **`P0/P1`×3** and **`P1/P2`×1**; 6 entries carry no band at
all (`#204`, `#323`, `#327`, `#315`, and two more), while `#99` carries `**P2**`
in a different position entirely — after a plan pointer rather than as a
`·`-separated field. So `priority TEXT NOT NULL CHECK(priority IN ('P0',…))`
rejects 11 real entries, and a positional parse misreads a twelfth.

**4. Origin has four states, not three.** 56 `human`, 41 `loop`, 8 explicit
`unknown`, and **60 with no origin marker at all**. `lint.py` enforces exactly
one marker on the 113 entries from #216 onward; everything older has none. The
contract reserves `**unknown**` for what predates the convention — so an
explicit `unknown` means *predates and was audited*, and absence means
*predates and was never touched*. `origin TEXT NOT NULL DEFAULT 'unknown'`
erases that distinction across 60 entries. This is the same shape as #289's
requirement that a missing review record be `unlinked` and never `pending`: **a
state the schema cannot represent gets silently merged into its neighbour.**

**5. The `·`-separated fields are not positional.** Extracting "the field after
the priority band" as `type` over all entries yields 65 distinct values,
including `landed 2026-07-27`, `origin: **loop**`, `origin: **unknown**` and
`**next-up**`. The genuine types are a small set (`idea`×31, `task`×12, `bug`×8,
`chore`×5, `feature`×4, `design`, `implementation`, `reliability`, …). So `type`
cannot be filled by position. Following #339's ruling on language markers — *a
misdetected value is worse than no value* — `type` is populated only from
unambiguous forms and left NULL otherwise, and the migration **reports** every
entry it could not classify instead of guessing one.

## Schema

Entry and identity are separated, which is finding 1's only honest answer:

```sql
CREATE TABLE entry (
  entry_id     INTEGER PRIMARY KEY,
  state        TEXT    NOT NULL CHECK (state IN ('open','landed')),
  title        TEXT    NOT NULL,
  body         TEXT    NOT NULL,   -- verbatim tail, never re-flowed (#281 renders it)
  priority     TEXT    NULL,       -- verbatim band incl. 'P0/P1'; NULL = none stated
  priority_rank INTEGER NULL,      -- derived: strongest band, so P0/P1 sorts with P0
  type         TEXT    NULL,       -- NULL = not unambiguously stated (finding 5)
  origin       TEXT    NULL CHECK (origin IN ('human','loop','unknown')),
                                   -- NULL = no marker at all (finding 4)
  source_line  INTEGER NOT NULL    -- provenance back into tasks.md.deprecated
);

CREATE TABLE task (                -- ids are permanent and never reused
  id        INTEGER PRIMARY KEY,
  entry_id  INTEGER NOT NULL REFERENCES entry(entry_id),
  ordinal   INTEGER NOT NULL       -- position within a combined entry: #138 then #156
);
CREATE INDEX task_by_entry ON task(entry_id);
```

`priority` keeps his words and `priority_rank` makes them sortable — two
columns rather than one because normalising `P0/P1` to `P0` for display would
edit his prose, and sorting on the text would put `P0/P1` after `P0` for no
reason a reader could defend. `priority_rank` is NULL for a stated-nothing
entry, and NULLs sort last explicitly rather than by whatever the backend does.

Dependencies are **not** parsed from prose. Today's blocked-on is free text
(*"blocked on #264 design and relevant #263 cutover decisions"*), and turning
that into edges is guessing:

```sql
CREATE TABLE dependency (
  entry_id  INTEGER NOT NULL REFERENCES entry(entry_id),
  depends_on INTEGER NOT NULL,     -- a task id, not necessarily an entry
  kind      TEXT NOT NULL CHECK (kind IN ('blocked_on','supersedes','cites')),
  evidence  TEXT NOT NULL          -- the exact substring it was read from
);
```

populated only from machine-recognisable forms, with `evidence` so a wrong edge
is traceable to the words that produced it, and every unparsed "blocked on"
phrase listed in the migration report for a human to convert or leave.

Review decisions, per #289 folded into #294:

```sql
CREATE TABLE review_decision (
  artifact     TEXT PRIMARY KEY,   -- one owning question: this IS the integrity rule
  question_id  INTEGER NOT NULL,
  decision     TEXT NOT NULL CHECK (decision IN ('pending','accepted','rejected')),
  decided_at   TEXT NOT NULL
);
```

`artifact` as PRIMARY KEY makes "exactly one owning question" a constraint
rather than a convention, so two questions claiming one artifact with
conflicting decisions is detected at write time. **`unlinked` is deliberately
not a value**: it is the absence of a row, reported by the read surface as a
distinct state. Storing it as an enum member would let a row exist that claims
no record exists.

## Read-only CLI surface

```
dreamwork tasks list [--state open|landed|all] [--sort priority|id|<key>] [--json]
dreamwork tasks get <id>              # resolves through task -> entry
dreamwork tasks count [--state …]
dreamwork reviews list [--json]       # includes unlinked artifacts as unlinked
dreamwork reviews get <artifact>
```

No write verb exists under this id, in any form, including a `--dry-run` one.

**The implementation language is an open decision, not Python (his note, watch
2026-07-28 01:05).** This section originally named verbs without naming what
implements them, and the unstated assumption was Python, because everything in
this skill is Python. That assumption is withdrawn rather than defended. His
criteria: *"a small (fast to load) portable binary + quick to recompile"* — which
are precisely the three Python fails, and a CLI the loop invokes on every tick
pays load time on every tick.

He also fixed the shape that makes the choice affordable: **git-style extension
dispatch**, where `dreamwork-thingy` on PATH is invoked as `dreamwork thingy`, so
*"we can have python modules (or go or rust or ocaml)"*. That converts the core's
language from a lock-in into an implementation detail — an extension in any
language is a sibling executable, not a plugin API to design. It also means the
read verbs above are the part that must be fast and small, while anything
elaborate can live outside the core.

Consequence for this document: the verbs, their output shape and the entity they
read are language-independent and stand as written. What is deliberately NOT
decided here is the core's language, the extension-discovery rule (PATH scan vs a
declared directory), and how a `--json` contract stays stable across
independently-compiled extensions. Those want their own IGC, and #294's
"do not pay for two migrations" instruction applies to the CLI surface too.

**And one thing must happen before any of it (#352).** His words: *"before we work
on this proper we should standardize the current python parsing so we fix the
duplicate code issues and such now in case it matters as we migrate and things."*
That is the duplication §"The invariant #294 says to verify" measured — two
`ledger_entries` implementations, three callers, one behavioural fixture. His
reason is the migration, and it is the strongest form of the argument: "re-point
the reader" is only a meaningful plan once there is one reader.

`list --state open` prints the landed count alongside, because #281's read
requirement says so and because an open-only list with no denominator is how a
queue silently overstates what is left. `get <id>` serves `?t=<id>` and must
return the **entry**, so both ids of a combined entry return the same body —
with the other id named, so a reader who asked for `#156` is told it shares
`#138`'s entry rather than quietly shown a body whose title says `#138/#156`.

## The invariant #294 says to verify rather than assume

#294 states the migration *"re-points #281's entry-level reader and nothing
else, which is only true while that reader stays the sole parser."* It is not
the sole parser now. Measured:

- **Two implementations.** `lint.ledger_entries` and `watch.ledger_entries`
  (`watch.py:6599`), whose docstring says *"lint.py's ledger_entries, VERBATIM
  (a test pins the two identical)"*. The logic is identical; the source is not —
  watch's copy drops the type annotations and rewrites the docstring, so a
  source-equality check would fail on a pair that behaves the same.
- **The pin is behavioural and single-fixture.** `test_watch.py:863` asserts
  `watch.ledger_entries(hostile) == lint.ledger_entries(hostile)` for one
  hostile input. That is a better pin than source comparison and a weaker one
  than it reads: one fixture cannot cover the space where two copies could
  diverge.
- **Three callers**, not one: `lint.py`, `watch.py`, and `task_origins.py`.

So the cutover consequence is concrete: re-pointing `watch.py` alone leaves
`lint.py` and `task_origins.py` parsing a file that cutover renames to
`tasks.md.deprecated`. Either the store's reader becomes the single
implementation all three call, or lint keeps a Markdown parser aimed at a
deprecated file and slowly becomes a checker of history. **The seam is the
reader, and there are three doors into it** — that is the finding, and it is
better learned here than at cutover.

## Migration: the parse-and-report half

Runs read-only, writes nothing, and answers: how many entries and ids, how they
split open/landed, which entries are combined, the exact histogram of bands,
types and origins, every entry whose band or type could not be read, every
"blocked on" phrase not convertible to an edge, and a digest per entry so a
later import can prove it carried the same bytes. It exits non-zero only on a
parse failure, never on an unclassifiable entry — those are output, not errors.

This is deliberately the useful half. It tells him what is in the ledger before
anything depends on the answer, and every finding above came from a rough
version of exactly this.

## Red-first acceptance fixtures

Each is stated as the production line that must change for it to fail, because
three checks in this repo have passed over the thing they were named for:

1. **A combined entry returns one body under both ids.** Fixture with
   `- **#138/#156**`; `get 138` and `get 156` return the same `entry_id` and
   each names the other id. Break by making `task.id` the primary identity —
   the test must fail on a duplicated or missing body.
2. **Entry and id counts are derived, never pinned equal.** The fixture opens a
   combined entry so the two differ, and asserts `ids > entries` at runtime.
   Break by asserting equality — it must fail on the fixture, which is the
   point of finding 2.
3. **A compound band survives and sorts with its strongest member.** `P0/P1`
   round-trips verbatim and ranks with `P0`. Break by normalising on write.
4. **Absent origin and explicit `unknown` stay distinguishable.** Fixture
   carries one of each; both are returned and they are not equal. Break with
   `DEFAULT 'unknown'` — must fail.
5. **An unreadable type is NULL, not guessed.** Fixture carries `#99`'s shape
   (band in the wrong position) and an entry whose second field is
   `landed 2026-07-27`. Break by filling `type` positionally.
6. **A missing review record reads `unlinked`, never `pending`.** Break by
   defaulting the decision.
7. **Two questions cannot claim one artifact.** The second insert must be
   refused by the store. Break by dropping the PRIMARY KEY.
8. **`list --state open` carries the landed count.** Break by omitting it.

## Open questions for him

Paired with a review artifact and a questions.md entry, per the standing rule.

- **S1.** Combined entries: keep them (entry/task split above), or split all
  three into single-id entries as a one-off before migrating and forbid new
  ones? The split schema is honest but every consumer then joins; forbidding
  them is simpler forever and edits three of his existing entries.
- **S2.** Should `priority` accept new compound bands after cutover, or is
  `P0/P1` an artefact to be resolved to one band as each entry is touched?
- **S3.** 60 entries have no origin marker. Leave NULL permanently as "predates
  the convention, never audited", or backfill to explicit `unknown`, which
  loses the distinction but makes the column NOT NULL?
- **S4.** Does `type` become a closed set at cutover (with the ~10 real values),
  or stay free text with NULL for unread?

--- SUMMARY ---

- Splits the ungated half of his sqlite steer out of #294 as #346: the task
  entity schema, the read-only CLI, and the migration's parse-and-report half.
  What #263 gates is how a *transition* becomes durable, which the columns
  describing a task at rest do not depend on.
- Five findings from the live ledger, each breaking an obvious schema: entries
  can carry two ids (3 real cases); the entry/id counts agree only by accident
  today; priority bands include `P0/P1` and 6 entries have none; origin has four
  states because absent and explicit `unknown` differ across 60 entries; and the
  `·`-separated fields are not positional, so `type` cannot be parsed by index.
- Schema separates `entry` (the body and its attributes) from `task` (permanent
  ids pointing at it), keeps priority verbatim plus a derived rank, and refuses
  to invent dependency edges or a `type` it cannot read.
- `unlinked` is the absence of a review row, not an enum value; one owning
  question is a PRIMARY KEY, so a conflicting second claim is refused.
- The "sole parser" invariant #294 says to verify is already false: two
  implementations, three callers, pinned by one behavioural fixture. Re-pointing
  watch.py alone leaves lint.py reading a deprecated file.
- Eight red-first fixtures, each naming the production line that must change for
  it to fail. Four questions for him (S1-S4), all about how much of today's
  looseness to preserve versus resolve at cutover.
