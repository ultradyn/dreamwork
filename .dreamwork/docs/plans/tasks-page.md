# A rich interactive `/tasks` page — design contract (#281)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. Read `watch-design.md` and
> `transitions.md` before touching the page; both are law and this document is
> subordinate to them.

**Goal:** give the durable task ledger a first-class home on the dashboard —
a `/tasks` list that is at least as well designed as the rest of the Web UI,
and a canonical task-detail URL that `#282` (inline `#N` hovercards) and
`#229` can hardcode.

**Architecture:** one new **deep module** turns a ledger entry into a
structured record, and everything else consumes records. `ledger_tasks(text)`
parses the file; `ledger_history(target)` exposes the per-id arrival/landing/
first-sight facts the existing `ledger_series` walk **already computes and
throws away**; `ledger_index(target)` merges the two behind one function,
cached on HEAD, and is the single swap point when `#294` re-points storage at
SQLite. The route-scoped `/tasksdata` endpoint serialises records; the client
router gains a `tasks` route whose param **is** the task id. The ledger stays
the sole authority — no second task database, no writes from this page.

**Tech stack:** Python 3 stdlib server/parser, the existing inline HTML/CSS/JS
app shell, pytest, one Playwright guard with its own planted git target.

---

## Global constraints

- `watch.py` stays one stdlib-only file; the page stays offline-clean, no
  build step.
- **Read-only.** `/tasks` adds no POST seam. The composer's `+` is already in
  every heading, and `do-now`/`add-idea` already exist; a row-level write is a
  new authority surface and is **out of scope by his ruling** — he asked what
  it would mean rather than approving it, and it has been re-asked as its own
  question (ruling 6). No increment below adds one.
- Every appear/disappear/expand/collapse/reorder/route change obeys
  `transitions.md` and **reuses an existing idiom** — no new mechanism.
- Every field the page renders is *parsed*, *derived* or **unknown**; an
  unknown renders as unknown, never as a blank that reads like a claim.
- `file-formats.md` gains the reader's grammar, and `lint.py` gains its check,
  in the same commit as the parser (`just audit-styleguide` measures it).
- A new check is not verification until it has been red for **its own stated
  reason**.

---

## 1 · Route and URL contract

### 1.1 The routes

| URL | Is | Title | Crumbs |
|---|---|---|---|
| `/tasks` | the list | `tasks` | `← dashboard`, counts |
| `/tasks?t=281` | **the canonical task detail** | `task #281` | `← tasks`, `dashboard` |

**Decision: the canonical detail URL is `/tasks?t=<id>`, digits only.**
Defended against the three alternatives, because `#282` will hardcode it and
`#133` may later prefix it:

- **`/tasks/281` (path segment)** — rejected. The server allowlist is an exact
  `parsed.path in (…)` membership test (`watch.py` — `("/", "/questions", "/answers", "/file", "/review")`). A path segment turns
  that into prefix matching, which is a change in *kind* to the one place that
  decides what this server will serve, and it lands in the same seam `#133`
  will rewrite. Query params keep the allowlist exact and get the prefix for
  free.
- **`/task?t=281` (a second route)** — rejected. Two routes for one subject
  means two `TITLES`/`crumbsFor`/`TINT`/`SEED` entries that can drift, and the
  list is the detail's parent: the crumb `← tasks` has somewhere to point
  precisely because they are one route.
- **`/tasks#281` (fragment)** — rejected. A fragment is not sent to the
  server and cannot be a route today; it also collides with the browser's own
  anchor behaviour.

It matches `/file?p=` and `/review?p=` value for value, and it fits the
router's existing `{name, param}` shape with **no router change** —
`routeOf` returns `{name:'tasks', param:'281'}`.

`t`, not `p`: `p` means "a path" on both existing param routes, and a reader
who sees `?p=281` will reasonably try `?p=some/file`. One letter, one meaning.

### 1.2 What else lives in the URL

Deep-linkable, because a filtered list is exactly the thing he wants to paste
or bookmark:

| key | is | example |
|---|---|---|
| `q` | free-text search | `/tasks?q=transition` |
| `f` | facet filter, comma-separated | `/tasks?f=open,P1` |
| `s` | sort key — **he sets it**, the default is only a default | `/tasks?s=oldest` |

**`s` is a user control, not a constant** (his ruling 2): the default is
priority-then-newest-id and he can change it from the controls row beside the
filters. Three consequences for the URL contract, all of which keep it
consistent with `?t=<id>`:

- **The default is never written.** `s` is absent at the default sort and
  present only when he has chosen another, exactly as `f` is absent at the
  default filter. A URL that spells out every default is a URL nobody can
  read, and `/tasks?t=281` stays the short canonical form `#282` hardcodes.
- **An unrecognised `s` falls back to the default and is dropped**, the same
  rule §Task 6 states for an unknown facet: ignored, never an empty list and
  never a 400. `?s=urgency` renders the default sort, and the next
  `replaceState` removes the key rather than preserving a value nothing
  honours.
- **Sort changes `replaceState` like the other two**, so choosing a sort does
  not add a Back step (§1.3). Reorder is a view of one list, not a
  destination.

Ephemeral, deliberately **not** in the URL: scroll position, which
disclosures are open, focus, and the caret. They are per-window state that
would make two windows fight over one address bar.

### 1.3 History semantics — the decision that keeps Back usable

**Search, filter and sort use `history.replaceState`; only a route change
(dashboard ↔ tasks, list ↔ detail) uses `pushState`.**

A keystroke is not a navigation. `pushState` per input event turns Back into
a fourteen-press walk backwards through his own typing, which is the failure
every faceted list on the web has; it also risks the browsers' pushState rate
limits. So:

- typing/filtering/sorting **replaces** the current entry — reload and paste
  keep the state, Back does not walk it;
- clicking a row **pushes** `/tasks?t=281&q=…` (the list state travels with
  it, so Back returns to the *filtered* list he left, not to a bare list);
- Back from the detail returns to that filtered list; one more Back leaves
  `/tasks` entirely.

`replaceState` is throttled to a ~150ms trailing edge with an immediate flush
on blur, Enter, and any navigation. The box is authoritative during the life
of the view; the URL is authoritative at route entry (first paint, deep link,
`popstate`). Stated because two copies of one value need a rule about which
one wins, and the failure otherwise is losing his last three keystrokes to a
tick.

### 1.4 Unknown, missing and stale ids

- `?t=9999` where no such id exists → **200, the detail view, saying so**:
  `no #9999 in this ledger` plus the highest id and a link back to the list.
  Not a 404: a 404 would make the client treat a legitimate route as broken,
  and the honest statement is about the *ledger*, not about the server.
- `?t=abc` / `?t=` / `?t=-3` → the same honest state, quoting what was asked
  for verbatim (escaped).
- `?t=138` where the entry is `- **#138/#156**` → the detail resolves, and
  says the entry numbers both ids. Either id is a legitimate address for it.
- **A landed-and-pruned id resolves.** Grooming prunes `## Recently landed`,
  so an id can be a real, permanent, completed task with no entry in the
  current file. It renders as `landed · entry pruned`, with the title from the
  last committed snapshot that held it and the landing date from git. This is
  the case `#282` most needs not to be a dead link.
- The tab title reflects it (`task #9999` / `task #281`), through one new
  `TITLE_ROUTE.tasks` entry.

---

## 2 · Data contract

### 2.1 The three functions, and why there are three

```
ledger_tasks(text)      → [record]      pure, text-only, no git, no I/O
ledger_history(target)  → {id: {...}}   git facts, from the EXISTING walk
ledger_index(target)    → {tasks, health, note, history_complete}
```

- `ledger_tasks` is the entry-level reader that does not exist today. Every
  current reader is **id-set level** (`parse_ledger` → sets, `entry_origins` →
  `(ids, origin)`, `ledger_entries` → `(ids, raw)`), which is why `#282` is
  blocked: there is nothing to hand it. It is pure so it is testable against
  hostile input with no repository at all.
- `ledger_history` does **not** add a walk. `ledger_series` already builds
  `arrived`, `landed` and `first_sight` per id and discards them at the end
  (which `#218` names in its own entry) — `watch.py:2042`. It returns them
  instead, memoised on the same immutable `(rev, rel)` snapshot key
  (`watch.py:1619`, which carries the tree-relative path for #217's reason and
  not the rev alone), and additionally keeps each entry's **title** per
  snapshot so a pruned task still has one. Cost: one extra dict per revision,
  at **288** ledger commits today and growing, and **no extra `git show`** —
  the walk already reads every snapshot's text.
  The memo tuple is `(open_ids, landed_ids, entry_origins)` today
  (`watch.py:1619`); §Task 2 extends it, and `_LEDGER_SNAPS` is keyed on an
  immutable commit so an extended tuple invalidates nothing.
- `ledger_index` is the merge, cached on HEAD exactly as `ledger_stats` is,
  and it is **the swap point** (§8).

**The grammar is `ledger_entries`, not a copy of it** — and the *reason* has
changed since this was written, which matters because the old reason is now
false and an implementer who checks it will conclude the rule is optional.

`#301` and `#315` widened the narrow readers. `LEDGER_ENTRY` is now
`^- \*\*(#\d+(?:/#\d+)*)\*\*` (`watch.py:1540`) — an **ids-only** bold span,
so it matches `- **#250/#251**` and `- **#292/#293**` and no longer drops
combined heads. So *"`LEDGER_ENTRY` cannot see a combined entry"* is **no
longer true** and is not the argument.

The argument that is still true is a different one, and it is the one §9.1
case 9 is about: `ledger_entries` walks `ENTRY_HEAD`
(`^- \*\*([^*]+?)\*\*`, `ledger_parse.py:37`), which is **wider** than
`LEDGER_ENTRY`. An entry whose leading bold token is *not* a bare id span —
`- **#7 stage 1** — …`, or a head with no digits at all — is still an entry
under `ledger_entries` (it yields `ids: []`), and would **vanish entirely**
under `LEDGER_ENTRY`. Vanishing is the failure this page cannot have: §3 lists
such an entry as `unknown` precisely because it exists. Zero of today's 148
entries take that shape, which is exactly why building on the narrow pattern
would look correct for as long as nobody wrote one.

**One hazard in composing them, and it is not theoretical — this review hit it
while measuring.** `ledger_entries` returns ids as **`int`**
(`[[331], [332], …]`), while `parse_ledger` returns them as **`str`**
(`{'50', '73', …}`, and its docstring says so deliberately, because
`ledger_series` and the origin walk key on strings throughout). So the obvious
composition — *is this entry's id in the open set?* — is `False` for **every**
id, silently, and the page renders 244 records all marked `unknown` while every
reader involved is working correctly. There is no exception and no crash to
notice. `ledger_index` must therefore **normalise once, at the seam, and state
which side it normalises to**; the record's `id` is an `int` because that is
what the URL contract and `?t=<id>` parse to, so the string sets are converted
on the way in, not the ints on the way out. §9.1 case 22 holds this.

What is pinned, stated precisely because the two guarantees are not the same
strength: `watch.LEDGER_ENTRY.pattern == lint.LEDGER_ID.pattern` and the same
for `ENTRY_HEAD`/`ENTRY_ID`/`ORIGIN_MARK`
(`test_watch.py:483`, `test_watch.py:840`) — **byte-identical patterns**. The
`ledger_entries` *function* is pinned by **output agreement on one hostile
fixture** (`test_watch.py:862-864`), not by byte-identity. That is enough to
catch a widening applied to one copy and not the other; it is not a proof the
two bodies are the same.

### 2.2 The record, field by field

**Coverage figures are re-measured at `16ef2e2`, 2026-07-27** — the ledger is
**148 entries** (106 open, 42 landed), 172KB of Markdown, **288 commits** of
history, **238 ids** ever named, of which **151 have a current entry**.

The `today` column is a **measurement with a date, not a constant**, and the
first pass of these figures aged out inside a day: the ledger was 121 entries
when this plan was written and the landed section held 17. So no check may
assert one of these numbers as a literal — §9.1's checks derive every count
they compare (the ceiling assertion in §4.1 is the one deliberate exception,
and it is a ceiling rather than a value).

Figures below are counted with the shapes this section states, at `16ef2e2`;
the implementation's own parse may land a few either way, and where it does the
implementation's number is the true one.

| field | source | rule | today |
|---|---|---|---|
| `ids` | leading bold token, via `ledger_entries` | every numeric id in it; a `#N` in the body is a cross-reference and numbers nothing | 148/148 |
| `id` | first id in `ids` | the display id; all of `ids` address the record | 148/148 |
| `section` | which `##` heading it sits under | `open` \| `landed`; an entry before any heading is `unknown` | 148/148 (106 open, 42 landed) |
| `title` | after the em dash, up to the first ` · ` | never truncated; if there is no ` · ` the whole remainder is the title | 148/148 |
| `annotation` | a leading balanced `[…]` before the title | lifted out so the title is the title; **unbalanced → no annotation** and the text stays in the title (fail toward keeping his words) | 9/148 |
| `priority_raw` | a chain token matching `P[0-3](/P[0-3])*`, **or** a bolded `**P2**` adjacent to the title | rendered verbatim, compounds included | 106/106 open — 102 as a chain token, **4 only in the bolded form**, so the bolded branch is not an edge case for one entry |
| `priority_band` | derived | the first recognised band in a compound (`P0/P1` → P0 — the entry is claiming at least P0). **Absent → P2**, the same middle-band rule as `questions.md`, and `priority_raw: null` so the page can say *unmarked* rather than implying an explicit P2 | all |
| `kind` | the chain token after the priority | free prose (`idea`, `Web UI bug`, `storage/tooling migration`) — recorded, never normalised into a closed set the ledger does not have | 106/106 open carry a token after the priority |
| `effort_raw` | a chain token that reads as a size | verbatim (`20m`, `several increments`, `2 parts`, `later`) | 64/106 parse to minutes; the rest keep prose |
| `effort_min` | derived from `effort_raw` | only `^\d+\s*(m\|min\|h\|hr)$`. **`4-5 increments` yields no number** — a digit-anywhere regex would report 4 minutes | 64/106 |
| `origin` | `entry_origins`' rule, verbatim | exactly one marker in `human`/`loop` is a claim; none, several, or wrong case → `unknown` | 59/106 open |
| `origin_first_sight` | git | the arrival classification (`#216`); first sight is final and never revisited | history-wide |
| `arrival_raw` | a `**human …**` / `**loop …**` stamp in the chain | verbatim, including the channel (`via watch \`add-idea\` 14:37`) | 52/106 |
| `arrival_when` | parsed out of `arrival_raw` | `YYYY-MM-DD` and/or `HH:MM`. **A time with no date stays a time** — no date is invented from the file's context | subset of the above |
| `first_commit` / `first_seen` | git | the first committed snapshot naming the id. **The only trustworthy filed-date** | history-wide |
| `landed_at` | git | the first snapshot naming the id under `## Recently landed`. Survives grooming, which the text claim does not | 114 ids |
| `landed_claim` | `landed <date>` in the entry text | the ledger's own claim. Shown **only** when git is unavailable, labelled as the ledger's claim | 34/42 landed entries |
| `sha` | a trailing `` `<7-12 hex>` `` | the landing commit the entry names; plain text, **not a link** (`#157`'s rule: a path/rev from an old commit may not resolve, and a link that 404s promises something) | 34/42 landed entries |
| `blocked_on` | `blocked on …` up to the next ` · ` | every `#N` in that span (`blocked on #264 design and relevant #263 cutover decisions` → `[264, 263]`) | 21/106 |
| `blocked_note` | the same span, verbatim | because some blockers are prose, not ids (`blocked on user-event model #263`) | 21/106 |
| `refs` | every other `#N` in the entry | cross-references, for the detail view's "mentions" | all |
| `description` | the remaining chain tokens | reflowed through `mdB`; **the whole thing, never a preview** | all |
| `raw` | the entry verbatim | **only on the single-record response**, never in the list payload (§4.3) | all |
| `present` | `false` for a git-only (pruned) id | with `title` from the last snapshot that held it | **87 today** — the common case, not a hypothetical |

**`present: false` is the case this plan most under-weighted, and the number
is the argument.** It was recorded as *0 today*, which made the whole pruned-id
path read as speculative machinery for a future grooming. Measured at
`16ef2e2`: git history has named **238 ids**; **151** have a current entry; so
**87 ids — 37% of every task this ledger has ever had — have no entry in the
file at all.**

The shape that produces them is documented and deliberate. Grooming compacts
`## Recently landed` into **column-0 prose roll-ups**, and
`file-formats.md:262-264` states outright that *"the column-0 prose summaries
under Recently landed are not entries and never join one."* So a landed task's
entry is replaced by a sentence naming it, and `ledger_entries` — correctly —
sees no entry.

Three consequences, each of which changes an implementation decision:

- **The list is built from the UNION of ids**, `ledger_tasks(text)` ∪
  `ledger_history(target)`, never from the file alone. §9.1 case 11 already
  says so and is now the check that covers 87 records rather than zero.
- **The snapshot title in `ledger_history` is load-bearing, not a nicety.** It
  is the only title 87 records have. §Task 2 must not be trimmed to skip it.
- **These records are in the list payload**, and the open-only default filter
  hides them. Excluding them from the payload instead would make the `landed`
  filter lie by 87 rows — a filter that silently under-reports is worse than a
  larger body, and the body cost is §4.3's problem to state, not to hide.

### 2.3 What is NOT detectable, stated plainly

`#281` asks for owner and for in-progress. The honest answers:

- **There is no owner field.** Ownership appears as prose inside descriptions
  (`**dreamer-qsec holds it**`). The page therefore renders **no owner**, and
  says the ledger has none, rather than regexing for `dreamer-*` and inventing
  a field. `#294` is where owner becomes a column.
- **In-progress is shown, it is labelled "in progress", and its evidence has
  to be structured.** His ruling 5 drops the *"this is a claim"* hedge, and
  that raises the bar on the evidence rather than lowering it: while the badge
  hedged, a loose read was merely vague; saying **in progress** makes it a
  statement, and a statement has to be right. So the page reads the signal
  from a **structured field that names an id**, never from prose.

  **Measured against the live file, prose is not usable, and it is worth
  showing why.** `.dreamwork/status.json` today carries
  `task: "TWO agents in flight on his two do-nexts: #269 … and #325 …. #326 …
  is diagnosed and queued behind #269's hold on watch.py."`, plus
  `current_task` naming `#327` and `coordinator_next` naming `#326`, `#281`
  and `#269`. An "is `#N` mentioned in status.json" test therefore marks
  **five** tasks in progress at once — and one of them, `#326`, is described
  in that very sentence as *queued*. That is a false statement on the page,
  which §3's own rule forbids, and it is the same defect as regexing
  `dreamer-*` into an owner column one bullet up.

  `agents[].in_flight` does not rescue it either, and for a subtler reason
  than a broken contract: it holds exactly what `file-formats.md:523` promises
  — *"one line: what it is doing right now"* — but **a line about the work is
  not a reference to a task.** Measured on the live file at `01df3b6`: of three
  agents, **two name no id at all**, and the third's line names `#281` while
  that agent's actual task is `#327`. So harvesting ids from it would attribute
  the wrong task and still miss the right one — worse than showing nothing.

  **So the evidence, in priority order, and the page shows nothing when
  neither exists:**
  1. **A structured id list in `status.json`** — `current_task_ids` at the top
     level and `task_ids` per agent, arrays of ints. This does not exist yet;
     it is a `file-formats.md` addition that the coordinator owns and it is
     recorded in §10 as required-but-not-made. Until it lands, this source is
     absent and contributes nothing.
  2. **The ledger's own `· in progress` chain token**, which the coordinator
     already writes — `#281`'s entry carries it today and it is the only
     entry that does. It is a parsed field like every other on the record, it
     needs no second reader, and it survives a target with no `status.json`.
  3. **Neither present → no badge.** Not "open, probably"; the row is simply
     `open`, which is what the ledger says.

- **"Reported: Xm Ys ago" is a measurement, and the formatter already
  exists.** `agePair(ct)` (`watch.py:1441`) renders exactly `05m 23s` — two
  units, each zero-padded, so the field never changes width — and `ages()`
  applies it to any `.age[data-ct]` node once a second (`watch.py:2756-2757`),
  which is also what keeps the number alive between ticks. **Do not author a
  second formatter**; this is the same one-idiom rule the rest of the page
  obeys.

  **What the age is the age *of*** — the moment the claim was written, not the
  moment the page rendered, because an age computed from `now` reads
  `00m 00s` forever and would be the exact hedge-dressed-as-a-fact his ruling
  removed:
  - ledger token → the commit time of the **first snapshot in which that
    entry carried the marker**, out of `ledger_history` (§2.2). Git-derived,
    so it survives grooming and cannot be rewritten.
  - `status.json` → the file's own **mtime**, which the server observes
    rather than the loop claims. `last_tick` is the loop's own claim about the
    same moment and is the fallback, labelled, when mtime is unavailable.
  - **No age available → the badge says so** (`in progress · when it was
    reported is unknown`) rather than showing a zero. An unknown renders as
    unknown here as everywhere else.
- **A task's own history is not visible beyond arrival and landing.** Nothing
  records a re-open, a re-prioritisation or a hand-off; `#264` is the design
  lane for a transactional transition history.
- **A shallow clone cannot see arrivals before its boundary.** The page says
  `coverage is incomplete` on its own line, exactly as the burndown does, and
  makes no broader claim (the `#216` lesson: describe the incompleteness you
  can *detect*).

---

## 3 · Honest task states, and what evidences each

One axis, as the question card has one: **who is this waiting on?**

| state | evidenced by | treatment |
|---|---|---|
| `open` | the entry sits under `## Open`, nothing else claims it | full ramp, the default |
| `in progress` | a **structured** source names the id: the ledger's `· in progress` token, or `status.json`'s `*_task_ids` once that field exists (§2.3). Never prose | the page's one accent here: a rail plus **`in progress`** — no hedge — and a hover/focus box reading `Reported: Xm Ys ago` |
| `blocked` | an explicit `blocked on …` in the entry text. **Never inferred** | one step down the ramp; blockers listed |
| `blocked · blocker landed` | as above, and every named id is in the landed set | says so: `blocked on #216 · which landed 2026-07-27`. The page does **not** silently unblock it — only the coordinator can |
| `landed` | the entry sits under `## Recently landed` now, **or** git says a snapshot once named it there and no current entry says otherwise | dim end of the ramp; carries the date and the sha |
| `landed · entry pruned` | git says landed; no entry in the current file | as above, title from the last snapshot |
| `unknown` | leading token parses no id, or no section can be determined | rendered **as unknown and still listed** — the entry exists, so it is reachable |

**The current file outranks history, and this needs saying because the two
disagree on a real id today.** The draft's evidence for `landed` was *"git says
… **or** the entry sits there now"*, and an `or` between two sources is not a
rule — it is whichever the renderer happens to test first. Measured at
`16ef2e2`: **`#275` is in the current open set AND in the ever-landed set**,
and that is not a bug in the ledger. Its research landed (`4b49ecb`) and a
snapshot named it under `## Recently landed`, but the task is legitimately open
because its ask awaits his approval, which its own entry states is part of its
definition of done. So:

- **A current entry's section is the answer.** History says only *"it was once
  listed as landed"*, and the coordinator is the authority on the present.
  `#275` renders `open`.
- **History answers only when the file does not** — which is the 87 pruned
  records (§2.2), where there is no current entry to outrank it.
- **The disagreement is shown on the detail view, never silently resolved:**
  `open · a snapshot once listed this as landed (2026-07-2x)`. Dropping the
  older fact would hide exactly the case where a task went back to open, which
  is the transition `#264` exists to record and nothing else can currently see.

**The partition, measured at `01df3b6`, because it is what makes `unknown`
first-class rather than a rarity:** of 244 records, **108 are open** (one of
them also ever-landed, above), **117 are landed and not open**, and **19 are
neither** — `#77, #95, #96, #102, #104, #106, #107, #108, #109, #110, #116,
#121, #123, #132, #141, #149, #151, #154, #157`. **Seventeen of the nineteen
are the multi-id-span gap** (§10). The other two are `#95` and `#96`, ids no
snapshot ever placed under either heading in a form any reader can see — and
`#96` is the one to keep in mind, because its only bold span is
`**#96 stage 1**`, which is prose and **must stay inert**: a widening that
admitted trailing words would start reading section titles as task ids. All
nineteen render as `unknown` **and are still listed**, because they exist.

**The `Reported:` box is a transition and obeys `transitions.md`.** It arrives
and departs on the existing hover/focus idiom; it is **not** hover-only —
§7's rule stands, so it opens on focus as well and the badge itself carries
the state, which is the part a touch reader gets without it. Nothing
load-bearing lives in the box: the age refines the badge, it does not replace
it.

Three rules follow and are worth stating because all three are easy to get
wrong:

- **A blocker that is missing is not the same as a blocker that landed.**
  `blocked on #999` where no such id exists renders `blocked on #999 · not in
  this ledger` — a wrong claim on the page is worse than an incomplete one,
  and this is exactly the shape of a typo nobody would otherwise notice.
- **"not in this ledger" needs a third state beside it, because the landed
  reader has a measured blind spot.** `_landed_ids` reads
  `LEDGER_COMBINED_MENTION` (`watch.py:1570`), an ids-only bold span joined by
  `/` **and only by `/`**. The landed section's compacted roll-up also writes
  **space-joined** spans — `**#121 #123**`, `**#104 #77**`, `**#109 #116**`,
  `**#107 #108 #110**`, `**#102 #106**`, `**#141 #149**`,
  `**#132 #151 #154**` — and one `+`-joined, `**#157 + #222 + #223**`. None of
  them match. Measured at `01df3b6`: **nineteen ids are in neither the open set
  nor the landed set** — `#77, #102, #104, #106, #107, #108, #109, #110, #116,
  #121, #123, #132, #141, #149, #151, #154, #157, #222, #223` — and **not one
  of them was in a landed set at any of the ledger's 295 revisions**, so
  walking history does not recover them either. So `blocked on #106` must
  **not** render `not in this ledger` — that is precisely the wrong claim this
  rule exists to prevent, and it would be wrong on nineteen real ids. The
  cross-check is three-way:
  **in the landed set** → `which landed <date>`; **in the open set** →
  `still open`; **in neither, but `ledger_history` has ever seen the id** →
  `state unknown` with no date. Only an id no snapshot has ever named earns
  `not in this ledger`. The reader gap itself is out of scope and filed (§10).
- **`blocked_note`'s prose is always shown**, because "blocked on user-event
  model #263" says more than `[263]` does, and dropping the words to keep the
  ids is the truncation failure in miniature.

---

## 4 · Search, filter and sort

### 4.1 Client-side, and where that stops being true

**Decision: filtering, search and sort run on the client**, over the
route-scoped payload. A few hundred records is a sub-millisecond scan; a
server round trip per keystroke would add a new endpoint shape, break the
deep-link model (the URL would no longer be sufficient state), and buy nothing
measurable.

**And it does not scale forever, so the ceiling is named rather than
discovered:** at **~600 records or a `/tasksdata` list body over ~512KB**,
whichever comes first, search moves behind `#294`'s query API.

**The denominator is records, not entries, and that changed the headroom.**
The record count is 148 entries **plus 87 pruned ids = 238 records** (§2.2),
and it is **monotonic**: grooming converts an entry into a pruned record
rather than removing it, so this number never falls. At 238 of 600 the
headroom is under 3×, where against entries alone it read as 4×.

**How the ceiling is asserted, because the obvious form is a check with an
expiry date:** the pytest measures the **real serialised body** of
`/tasksdata` against a planted ledger *and* against the repository's own, and
asserts `len(body) < CEILING`. It must not assert today's size — that is a
literal tuned to today's fixture, the trap `CLAUDE.md` names — and it must
derive and **print** the current size so the number in the output is today's.
The ceiling is the one constant here, and it is a constant on purpose.

*(Both figures the earlier draft quoted — 103KB of Markdown, a 139KB payload —
were measured at `c1f5aaa` and are stale: the ledger is now 172KB. See §4.3.)*

### 4.2 The controls

- **Search** — one `<input type="search">`, matched case-insensitively
  against id, title, kind, description and blocker prose. Substring, not
  fuzzy: a fuzzy match that surfaces an unexpected row is a page you stop
  trusting. `#281` and `281` both find the task.
- **Filter** — the standing sliding group (`.sgroup`/`.sgind`/`.sgbtn`), so
  geometry, motion and the ghost-outline rule are free. Two groups: **state**
  (`open` · `blocked` · `landed` · `all`) and **priority** (`P0-1` · `P2` ·
  `P3` · `any`). Multi-select within a group is a `,`-joined `f` value.
- **Sort — a third group in the same controls row, on the same `.sgroup`**
  (his ruling 2: *"user configurable alongside filters"*). `priority`
  (default), `newest`, `oldest`, `effort`; single-select, because two sort
  keys at once is a claim about tie-breaks the reader cannot see. It is the
  same component as the two filter groups and it sits beside them rather than
  in a menu of its own: a control he has to open is a control he does not know
  he has, and the whole point of his ruling is that the ranking stops being
  the page's opinion.
  `effort` puts the un-estimated tasks in a **labelled tail**
  (`no estimate · N`, the count derived at render) rather than sorting them as
  zero or hiding them: `nothing is dropped, only demoted`.

  **Three groups is the row's budget, and it is spent.** At ≤540px the row
  stacks (§7); a fourth group would make the stack taller than the first two
  rows of results, which is the point at which the controls stop serving the
  list. Any later facet is a value inside an existing group, not a new one.
- **The count line is always present** and names the denominator:
  `38 of 106 open · 113 landed`. It is an `aria-live="polite"` region, which is
  the screen-reader equivalent of watching rows travel (§7).

### 4.3 The payload

New GET `/tasksdata`, allowlisted beside `/filedata`:

- `/tasksdata` → `{generated, health, note, history_complete, tasks:[…]}`,
  **without `raw`**. `raw` is the entry verbatim and `description` is nearly
  all of the same bytes, so carrying both roughly **doubles** the list body
  for a field only the detail view reads. The earlier draft's figures (139KB
  without, 226KB with, *"63% of the body"*) were measured at `c1f5aaa` and are
  doubly wrong now: the ledger has grown 67% since, and 87KB of 226KB is 38%
  of that body — 63% was the size of `raw` **relative to the body without
  it**, which is not what the sentence said. **Both numbers are to be
  re-measured in §Task 3 against the real serialised body**, printed by the
  test, and neither is to be quoted here as a constant.
- `/tasksdata?t=281` → `{task: {…, raw}}` or `{task: null}`.

**It is a route-scoped fetch, not a `/data.json` field.** `/data.json`
measures **456,842 bytes at `16ef2e2`** (up from 374KB when this was written)
and is re-fetched every ~2s on every open window; adding the parsed ledger to
it would put the whole task text on the wire every two seconds for the benefit
of one route. Its own composition says why it must not grow: `files` is 184KB
of it (`lessons.md` 90KB, `questions.md` 85KB), `dreams_archive` 132KB,
`answered_entries` 55KB. `/filedata` is the standing precedent for exactly
this. The client caches it and invalidates on a changed `/mtime`, so liveness
is unchanged and the cost is paid only where it buys something.

`#282`'s hovercards fetch `/tasksdata?t=N` for one record and cache it — which
is why the single-record shape exists at all.

---

## 5 · Composition and visual design

In `watch-design.md`'s vocabulary. Every component named below already exists.

### 5.1 The column, and the seam `/tasks2` composes

**`/tasks` is one 72ch column, centred, as every reading view** — his ruling,
not a refusal of the wide layout. The wide two-pane list-plus-detail triage
layout is **approved and lives at `/tasks2` (`#328`)**, which is why this page
does not need to be two things: he gets the reading column at one address and
the triage bench at another.

`watch-design.md` records `/review` as the styleguide's one width exception
(`watch-design.md:158-161`, `:613`), so `/tasks2` adds the second and must say
so in that document when it lands — that is `#328`'s obligation, not this
plan's.

**What this plan owes `#328` is a seam, and it is exactly three things**, each
of which this plan already produces for its own reasons:

- **`ledger_index(target)` and the record shape** (§2) — `/tasks2` reads the
  same records through the same `/tasksdata`. It adds **no second parser and
  no second endpoint shape**; the constraint in §8 binds it identically.
- **`taskRow(t)` and `taskFacets(t)`** (§5.2) — the list pane is this page's
  row, unchanged. A row that only renders correctly inside a 72ch column
  would force `#328` to author a second one, so the row is written to lay out
  in its container rather than against the page.
- **`buildTaskDetail(t, d)`** (§5.3) — the detail pane is this page's detail
  view, called with a container instead of a route. Keeping the builder
  container-agnostic is the whole seam; it costs nothing here.

**And `/tasks2` inherits `/review`'s split idiom rather than authoring a
second one.** `#305` reworked that pane and the machinery is now specific and
reusable: a window-tall two-column pane measured by `fitReview` into `--rvh`
(layout, via `offsetTop`, never a rect read through the dissolve's
transform), the gutter promoted to a keyboard-operable `role="separator"`, the
ratio clamped in CSS as `clamp(32ch, var(--rsplit), calc(100% - 26ch))`, the
width persisted in `localStorage['dw.review.split']` and emitted into the
markup so a fresh load *paints* at his width, and a `@media (max-width:900px)`
branch that goes back to one document rather than crushing two columns
(`watch-design.md:192-322`). None of that is this plan's work; naming it here
is what stops `#328` from re-deriving it.

### 5.2 The list

`pageHeader` (with the `+` opener) → the controls row → the count line →
`<ol class="tasks">` of rows. `label` supplies the dim uppercase furniture.

**A row is a two-part block link** (`.tk[data-tid]`):

```
#281  add a rich interactive /tasks page                        P1
      dashboard feature/design · human · filed 2026-07-26 · 60m
```

- line 1: id (`--dim`), title, priority at the right edge;
- line 2: the facet chain at `--dim`, one step below the title.

Three things about it are decisions, not defaults:

- **No description preview on the row.** Every field on a row is *whole or
  absent*. A truncated body is what `#106` looked like from the outside — a
  "confusing cut-off preview" that was really data loss — and a summary that
  might be complete is worse than one that obviously is not. The whole
  description is one click and one URL away, which is what "ranked, never
  withheld" asks for.
- **Priority is luminance, not colour.** `P0/P1` at `--bright`, `P2` at
  `--text`, `P3` at `--dim`. Emphasis on this page is the text ramp; spending
  a hue on priority would put four colours on a page that has two.
- **The facets are inside the link.** That makes the whole row one tap target
  (~40px at phone width, where the chain wraps under the title) and makes the
  accessible name the whole row, which is what a keyboard reader wants.
  Consequence, accepted deliberately: **blocked-on ids are plain text on the
  row** (no nested links inside `<a>`) and become links on the detail view.

### 5.3 The detail view

`TITLES.tasks` gives it the heading; the body is:

- the title block (the morph's hero — §6.3);
- a **fixed-key-column** fact grid, the status panel's rule (`#130`): a long
  key wraps inside its own column rather than shoving that row's value out of
  line. State · priority · kind · effort · origin (recorded **and** first
  sight, when they differ, each labelled) · filed · landed · sha · ids;
- **blockers, both directions** — `blocked on` and `blocking`, each a link to
  `/tasks?t=N` with the blocker's own state beside it, because "blocked on
  #216" is useless without knowing that #216 landed;
- the description, reflowed through `mdB` (backticked paths become `/file`
  links, review artifacts become docked `/review` links — free, via
  `linkify`);
- `mentions` — the other tasks this entry references and the ones that
  reference it;
- a final `expand` peek: **the raw entry text**, verbatim in a `<pre>`. The
  ledger is prose and a reader should be able to see the bytes the page
  parsed; it is also the honest escape hatch for every field the parser
  demoted into `description`.

### 5.4 Colour, stated because both loud colours are enumerable

- **`--accent` is spent on exactly one thing: the `in progress` rail.** It is
  the only live, in-flight fact on this page. Everything else here is work for
  the *loop*, not an errand for him, which is the burndown panel's rule
  (`#142`) one surface over. It does **not** breathe — the awaiting-fold wisp
  stays the page's one continuously moving exception.
  The `Reported: Xm Ys ago` box spends **no** second colour: it is `--dim`
  text on the panel, because the age qualifies the accent rather than
  competing with it.
- **`--warn` appears in exactly one state: a `tasks.md` the reader cannot
  see** — amber, on the rail, with the line count and the path as a `/file`
  link. This is not a third use of amber: it is `#136`'s use (a file the
  reader cannot see, so a channel has silently failed) on a second file. The
  reasoning is stated in `watch-design.md` so the next reader does not have to
  re-derive whether it qualifies.

### 5.5 The three kinds of nothing

`#136`'s pattern, because "nothing to show" and "the reader is broken" produce
the same empty list:

| state | when | treatment |
|---|---|---|
| `missing` | no `.dreamwork/tasks.md` | one dim line. A target that keeps no ledger has not failed at anything |
| `unreadable` | content, and `ledger_entries` sees no entries | **the fault** — `--warn`, the rail, the line count, the path as a `/file` link |
| `no match` | the ledger is fine, the filter matches nothing | `nothing matches "xyz" · 238 tasks in the ledger` (the denominator derived, never a literal) and a one-click clear. **Never collapsed into "no tasks"** |

---

## 6 · Motion

Per `transitions.md`. Nothing below is a new mechanism.

### 6.1 Route entry and exit

The dream dissolve, with `TINT.tasks` and `SEED.tasks` entries of its own:
**`-0.30` and `13`**, re-checked at `16ef2e2` against the full current sets —
tints `dashboard 0, questions .14, answers .08, file -.14, review .22`
(`watch.py:3086`) and seeds `7, 23, 29, 41, 61` (`watch.py:3090`). Both
proposed values still collide with nothing.

A destination without its own signature silently shares another's through
`TINT[name] || 0`. That was a live gap for `/answers` when this was written and
**`#302` has since fixed it** (§10), so `/tasks` is now adding the sixth
signature to a complete set rather than the fifth to an incomplete one — there
is no precedent here for skipping it.

### 6.2 Rows arriving, departing and reordering

**This is `#104`'s regroup over a FIFTH keyed list, and it must be the same
`snapshotCards`/`regroupCards` pair** — a second implementation of "one
leaves, its neighbours travel" is two things to keep true. Four descriptors
exist today, not two: `QA_LIST`, `ANSWER_LIST`, `GIT_LIST` and `REVIEW_LIST`
(`watch.py`). The draft called this the third; it is the fifth, and
the correction matters only because "third" was the argument that one more
user of one mechanism is unremarkable — with four already there, it is more
unremarkable, not less.

```js
const TASK_LIST = { sel: '.tk[data-tid]', key: 'tid' };
```

- **He filters or sorts** → snapshot, mutate, regroup. Survivors travel to
  their new positions (in position and height); rows leaving `dreamAway` at
  the rect they occupied; rows arriving snap with `.dreamin` and ease in.
  Neighbours travel **up** to close a gap, so departures rise — the question
  list's sign, not the commits panel's (`#174`: a departure leaves in the
  direction its list travels).
- **A live tick changes the list** → the new DOM commits immediately
  (liveness never waits), and whatever survived and moved travels. Identical
  to the questions list.
- The row fixed-height/ellipsis rule of the commits panel does **not** apply:
  a task row is two lines and its height is stable, so `dh` is 0 in practice
  and neither body branch of `regroupCards` is reachable — inert by
  construction, as `.git .commit` already is.

### 6.3 List ↔ detail

The **lifted-hero morph** (`flipDock`) over the dissolve, which is the same
gesture a question card already makes into the review dock: the clicked row's
rect is passed as `opts.fromRect`, and the detail's title block is the hero,
lifted above the dissolve so it reads as *that row travelled* rather than
"page changed, thing appeared".

- **Back morphs too**, using the same helper with source = the detail title
  block and destination = the row's rect after the list renders. Same
  algorithm, opposite ends.
- **It fails to the simpler gesture, never to a wrong one:** if the row he
  returns to is filtered out of the list he lands on, there is no destination
  and the transition is the plain dissolve.

### 6.4 Disclosures

The detail's raw-entry peek uses `foldDetailsLocal` (`watch.py`) — height
travel through `travelCard` + `revealBody` arrival + `dreamAway` departure at
the rect it occupied, the section-fold pieces, and it takes the reduced-motion
branch (`if (rmr) { det.open = !det.open; return; }`) for free.
`box-sizing:border-box` while the height animates comes from `travelCard`
itself (`watch.py:~3998`), so it is inherited rather than restated — do not set
it a second time here. It does **not** get a
`data-keep` list key it cannot honestly own; it opts into the fold snapshot
with `data-keep="task:281:raw"`, which is content-addressed by the id, so open
survives the tick and cannot re-open the wrong record.

`#297` covers the plain `expand()` peeks elsewhere; this page adds none.

### 6.5 Reduced motion

Route swap instant, no ghost, no mist, tint/seed snap. Rows **place** rather
than travel. The morph is skipped. **Function is identical** — filtering still
filters, sorting still sorts, focus still moves, the count still updates, and
`.dreamin` is never applied as a start pose (`#293`: it is a start pose, not a
skin, and a stuck one leaves rows invisible and still clickable).

---

## 7 · Accessibility and input parity

- **Semantics.** `<ol>` labelled `open tasks · 38 of 106`; one `<li>` per
  record; the row is a block `<a href="/tasks?t=281">` whose accessible name is
  the whole row. Facet tokens carry visually-hidden prefixes only where the
  bare value is ambiguous (`filed 2026-07-26`, `origin human`).
- **The count line is `aria-live="polite"`.** A sighted reader watches rows
  travel; a screen-reader user hears `38 of 106 open`. Without it, filtering
  is a silent event, which is the same class of failure as a fold that hides
  something in flight.
- **Keyboard.** Rows are links, so Tab/Enter/middle-click/new-tab work with no
  JS (modified clicks already fall through `isInternal`). `Escape` in the
  search box clears the filter (and replaces the URL). No modal keymap is
  invented.

  **`/` is the page's first bare single-key global hotkey, and the draft
  under-stated that.** It cited *"the same rule the shader hotkey already
  obeys"*, and there is no shader hotkey: the main document's only keydown
  handlers today are `Escape` for the command palette (`watch.py`) and
  Ctrl/Cmd+Enter to submit from a text field (`watch.py`). The one bare
  single-key handler in the tree is the **debug layer switcher's `l`**, and it
  lives in a popout (`watch.py`) rather than on the main document. Its
  guard is the idiom to copy verbatim, comment included — *"never hijack a
  keystroke aimed at a text field"*:

  ```js
  if (e.target.closest && e.target.closest('input, textarea, select')) return;
  ```

  Being the first of its kind is the reason phase J is not optional: a bare
  letter or symbol bound at the document is one keystroke away from eating a
  character out of the composer, which is the class of loss `#269` is open on
  right now.
- **Focus management, which the page has never had to do before.** After *his*
  navigation to a detail, focus moves to the detail's title block
  (`tabindex="-1"`), so the new subject is announced; after Back, focus returns
  to the row. Focus moves **only** on a navigation he initiated — never on a
  tick, which is `#179`'s rule (`refocus()` restores, and restore only ever
  re-opens or re-fills).
- **Touch.** The whole row is the target; at ≤540px the facet chain wraps
  under the title, giving a ~40px row without a `pointer:coarse` special case.
  Nothing load-bearing is hover-only — hover is the weakest of the three
  detail idioms and this page uses it for none of them.
- **Responsive.** 72ch column; controls stack at ≤540px; the detail's fact
  grid becomes stacked label-above-value pairs; the raw peek scrolls in its
  own box rather than pushing the page sideways.
- **His state survives any re-render.** The search box's *value* is
  reconstructible from the URL, so the only state existing nowhere else is
  the caret, the selection and the focus — carried by
  `snapshotTaskFilter`/`restoreTaskFilter`, mirroring `snapshotAskState`
  exactly, and running **before** the regroups (which measure) and **after**
  `restoreFolds` (which nests). A new render path must state how it satisfies
  this rule; this paragraph is that statement.

---

## 8 · Relationship to `#294` and `#264`

**The swap point is `ledger_index(target)`.** Nothing above it reads
`tasks.md`, and nothing below it renders. When `#294` lands, that one function
returns records from SQLite and `ledger_tasks` becomes the migration's
importer — the view does not change.

What this page must **not** assume, each because `#294`/`#264` will break it:

- **not** that ids are dense, contiguous, or that `max(id) + 1` is next;
- **not** that a record's fields came from text — `origin`, `first_seen` and
  `landed_at` are fields on the record, so a transactional store fills them
  from its own history instead of from git;
- **not** that file order means anything. The page sorts explicitly. Today's
  file order (descending id under `## Open`) is used **only** as the stable
  tie-break, and it is named as "as written" rather than as chronology;
- **not** that the ledger is a git checkout at all (a target may not be), which
  is why every git-derived field is optional and its absence is a stated
  state rather than a blank;
- **not** that there is one writer. This page never writes, so it cannot
  corrupt a concurrent transition; it may show a stale read for one tick,
  which is what every other panel here already does.

Conversely, what `#294` inherits from this contract: the record shape, the
`/tasks?t=<id>` URL, and the `/tasksdata` response envelope. Those three are
the public surface `#282` and `#229` hardcode, so they are the parts `#294`
must preserve or migrate deliberately.

---

## 9 · Verification plan

There is no CI; `just test` is it. **Every check below names the bug that will
be reintroduced to see it red**, because checks in this repo have a documented
habit of passing over the thing they were written for.

### 9.1 pytest (parser and server) — `test_watch.py`

| # | asserts | red by |
|---|---|---|
| 1 | a combined entry yields ONE record addressable by either id | **the old injection no longer reddens this** — `LEDGER_ENTRY` is combined-aware after `#315`. Red it by building on `LEDGER_COMBINED_MENTION` with a space-joined head, or on an `ENTRY_ID.findall` over the head that yields the ids as two records rather than one |
| 2 | a `#N` in a body numbers nothing | `ENTRY_ID.findall(whole_entry)` |
| 3 | origin fails closed: two markers → unknown; `**Human**` → unknown | taking `marks[0]` without the count/vocabulary test |
| 4 | a hard-wrapped metadata chain parses (`origin:` ending a line) | parsing per physical line instead of joining the entry |
| 5 | `P0/P1` → band P0, raw preserved; absent → band P2 with `priority_raw: null`; `**P2**`-before-title is found; `P4` → no band, raw kept | `int(tok[1])`, or defaulting `priority_raw` to `"P2"` |
| 6 | `20m` → 20; `4-5 increments` → **no** minutes, raw kept | a digits-anywhere regex (reports 4) |
| 7 | `blocked on #264 design and relevant #263 cutover` → `[264, 263]` + verbatim note | anchoring the pattern at end-of-token |
| 8 | the blocker cross-check is **three-way**: in the landed set → `blocker_landed`; in the open set → `still open`; known to history but in neither set → `state unknown`; named by no snapshot ever → `blocker_missing` | collapsing the third state into `blocker_missing` — which is wrong today on nineteen real landed ids (§3, §10). **Assert the precondition:** the fixture's four blockers must land in four different states, derived at runtime, or three of the four branches are untested and the check still passes |
| 9 | an entry whose leading token has no digits yields `ids: []`, state unknown, **and is still listed** | `ids[0]` → IndexError → the whole route 500s. **Assert the precondition:** today's ledger holds **zero** entries of this shape (measured at `16ef2e2`), so the case is reachable only from the planted fixture — the test must build the entry itself and assert it is absent from the real ledger, or it is a check whose subject may quietly stop existing |
| 10 | landing date comes from git; with no repository, the text claim is shown **labelled** | reading only one of the two → a pruned entry has no date, or a non-checkout shows nothing |
| 11 | a git-only (pruned) id appears with `present: false` and a snapshot title | building the list from the file alone. **87 records take this path on the real ledger** (§2.2), so the check also asserts the union is strictly larger than the entry set — a fixture-only assertion would have passed while the real page dropped a third of its records |
| 12 | `/tasksdata` omits `raw`, and the list body is under the stated ceiling | including `raw`. The check **prints** the measured body size and compares it to the ceiling constant, never to today's value (§4.1) |
| 13 | `/tasksdata?t=9999` → 200 `{task: null}`; `?t=abc` likewise | returning 404 |
| 14 | `/tasks` and `/tasks?t=1` both serve the shell (allowlist) | leaving the allowlist unchanged |
| 15 | `ledger_series`' existing outputs are byte-identical after the refactor | changing a bucket boundary while exposing the maps |
| 16 | `lint.py` WARNs on a token that reads as a priority and parses to no band, reading the band rule **from watch.py** | giving the linter its own copy of the rule (the exact drift `#197` paid for). The precedent is now in the tree: `check_priorities` asks `watch.title_priority` and never re-derives (`lint.py:243-252`, `:266`) — the task-band function is a **second** rule and needs its own single copy, not a reuse of the question one |
| 17 | the `s` codec round-trips, an unrecognised `s` renders the default sort **and is dropped from the URL**, and the default is never written | honouring an unknown key (a sort nothing implements) or spelling the default into every URL — which would break the `?t=281` canonical form `#282` hardcodes |
| 18 | `in progress` comes from a **structured** source only: the ledger's `· in progress` token, or `*_task_ids` when present. A `status.json` whose `task` prose names three ids marks **none** of them | matching ids out of prose → the live file marks five tasks in progress, one of which it calls *queued* (§2.3). Build the fixture from the real file's shape, and assert the prose names ids the badge does not claim, or the check cannot fail |
| 19 | the reported-age is the age of **the claim**, not of the render: an `in progress` marker planted N seconds back reports ≈N, not zero | computing the age from `now` → every badge reads `00m 00s` forever, which is the hedge his ruling removed wearing a number |
| 20 | an id under `## Open` whose history also names it as landed renders **`open`**, with the older fact stated and not dropped | testing history first (or an `or` between the two sources) → `#275` renders landed today while its entry describes live work. **Assert the precondition** that the fixture id really is in both sets, derived at runtime |
| 22 | an id that is open **and** has an entry renders `open`, proving the entry set and the open set were joined on the same id type | comparing `ledger_entries`' `int` ids against `parse_ledger`'s `str` ids → the join is empty and EVERY record renders `unknown`. **Assert the precondition:** the test derives one id from each reader and asserts the raw values are unequal while the normalised ones are equal, so the case cannot pass by both readers happening to agree |
| 21 | an id known to history but in neither set renders `unknown` **and is listed** | filtering the record set down to open∪landed → nineteen real ids vanish from a page whose whole claim is that nothing is dropped |

### 9.2 Browser guard — `dev/capture/tasks.mjs`

**It builds its own git target and takes an ephemeral port.**
`dev/capture/fixture` is not a repository and holds no `tasks.md`, so every
check against the shared server would pass against nothing — the trap
`burndown.mjs`, `provenance.mjs`, `gitrow.mjs` and `dashboard.mjs` each name.
The fixture is **not** extended: seeding it can make a *neighbouring* guard
vacuous without making it red, which is the worse failure. History is planted,
so the numbers are known rather than read off the page and compared to itself.

**It is written on `dev/capture/report.mjs`, which did not exist when this plan
was drafted.** `#192` landed the shared reporter (`9fcbcda`), and the whole
point of it is that a new guard inherits the four obligations by construction
instead of being written without them — the count of unconverted guards was
17 of 39 eighteen minutes before it was measured as 18 of 40, because *every
new guard* was one. So:

```js
import { makeReporter } from './report.mjs';
const { ok, present, declare, finish, checks, notes, errs } = makeReporter();
declare({ drives: '/tasks list + detail, filter/sort/search, the morph, a real tick',
          traceWindow: '…and why that bound is the interaction, not a tick' });
```

- **`declare({drives, traceWindow})` is mandatory and THROWS on a missing
  half** (`report.mjs:112-121`). The trace window is not documentation: a guard
  that watches long enough sees a later tick supply the motion it was asserting,
  which is how `regroup.mjs` traced 5.2s past a 1.6s `holdRerenderUntil` and
  went green over a teleport.
- **`present(page, sel, what)` replaces the plan's hand-rolled absence check** —
  it prints one named FAIL in seconds where a Playwright timeout costs 30s and
  points at the guard rather than the page.
- **The crash sentinel is the exit handler**, so a partway crash still prints
  the checks plus `FAIL the guard threw before finishing its checks`; the guard
  calls `finish()` at its successful end. Forgetting `finish()` makes a crash
  visible, which is the point.
- **No count, ever.** The module prints `checks.join('\n')` and offers no tally,
  because a `grep -c` once reported 6 FAILs where the output held 14. Do not
  add one.
- Add `tasks` to `DEFAULT_GUARDS` in the justfile (`justfile:135`) and to the
  header's own-target notes, as `burndown` is.

| phase | asserts | red by |
|---|---|---|
| A route | direct load of `/tasks?t=281` renders the detail, the title reads `task #281`, the crumb is `← tasks` | routing param-less → the list renders |
| B filter motion | on a real typed keystroke: **at least one frame of each surviving row sits part-way between its old and new position** (`between(vals, first, last)`, ~3% deadband), with the row's travel span derived, printed, and asserted above a literal floor; every departing row leaves a ghost at its own rect; and **no frame goes past the final position**. Trace bounded to the interaction | rebuilding via `innerHTML` with no regroup → **zero** part-way frames |
| C reduced motion | same filter: **zero** part-way frames, **and** the same final row set, the same count line, focus still moved | skipping the RM branch (a part-way frame appears) or letting RM skip the filter (function lost) |
| D morph | clicking a row: the hero node was **never replaced** across the window, at least one frame part-way between the row's rect and the title's, and no frame past the final rect | navigating without `fromRect` |
| E history | type `foo`, open a row, Back → the filtered list returns; one more Back leaves `/tasks`. Assert `history.length` grew by **one** across the typing | `pushState` per keystroke → Back walks his typing |
| F survives the tick | half-typed search + an open raw peek, then a forced real tick (`POST /command`): assert the row nodes **were replaced** and that value, caret, focus and the open peek all survived | omitting the snapshot pair, or running cards before folds (`#179`) |
| G stale blocker | planted `blocked on #216` with #216 landed → the row says the blocker landed; planted `blocked on #999` → says not in this ledger | rendering a bare `blocked` |
| H unknown id | `/tasks?t=9999` states it honestly, the list stays reachable, the title says so | rendering an empty detail |
| I focus | after his navigation focus is the detail title; after Back it is the row; after a **tick** it has not moved | moving focus in `setContent` |
| J hotkey | `/` focuses search; `/` typed inside the search box inserts a slash | no target guard |
| K colour audit | `--accent` resolves on the `in progress` rail and nowhere else; `--warn` only in the unreadable state | accenting priority (the sabotage `status.mjs` used) |
| L three nothings | missing / unreadable / no-match render three distinguishable states | collapsing no-match into no-tasks |

Resolve `--accent` through a throwaway element, not off `:root` — the token is
authored as `#a5b4fc` and every computed colour comes back `rgb(…)`, so the
naive comparison matches nothing and passes on a page painted entirely in it.

**The motion phases above are written in `transitions.md`'s current form, and
the earlier draft's form is now forbidden.** That document's *Checking a
transition* section (`transitions.md:21-140`) has moved on, and phases B, C and
D as first written specified precisely the idiom it names as a mistake. Five
existing guards were converted away from it. What it now requires, each with
the reason:

- **Never assert an absolute COUNT of distinct positions.**
  `uniq(positions).length >= 8` says *"this machine rendered eight frames in
  850ms"* — a fact about the box, not about the motion. `headertravel`'s 1s
  glide gave 5 part-way frames of 31 idle and **2 of 14** under six CPU
  burners, so a floor of 2 was already on the line. Guards went red on a
  commit that was fine, twice, at two different loads.
- **The floor is ONE part-way frame** — not a fraction (tuned to the trace
  window) and not a bigger count. Zero-versus-some is the entire distinction
  between a snap and a travel. Whether the travel is too *fast* is the
  no-frame-past-the-end rule's question and must not be smuggled in here.
- **A part-way count needs a vacuity precondition, and that one IS a
  literal.** `between(...) >= 1` passes on a 2px twitch, so assert the travel
  span first. Derive and print the real span so the printed number is today's;
  keep the floor a constant so it fails when the subject stops moving. This is
  the one place the never-a-literal rule does not apply.
- **Copy the `between` helper, not a file.** It is deliberately one idiom
  (`reviewsplit.mjs:145` is the original; `headertravel`, `regroup`, `morph`
  and `qsec` carry it verbatim). `qsec` spent a day holding both forms and read
  as a considered distinction rather than an unfinished job.
- **Do not round a per-frame trace.** Rounding a clean 2.1px ease reported it
  as a snap. `reviewsplit.mjs`'s `distinct()` rounds and is only safe because
  its travel assertions require ≥60px — so either keep raw values or state the
  minimum travel the rounding tolerates.
- **Do not anchor an arrival to a clock**, and do not assert a terminal state
  inside a fixed sampling window: `dismiss.mjs:134`'s `ops.at(-1) >= 95`
  reddens over a perfect animation on a slow box. Wait on the transition's own
  completion (`getAnimations()`, `transitionend`) and then assert.
- **Never measure geometry beneath a mid-transform ancestor.** The dissolve
  scales, so every rect under it reads ~3% small with the error multiplying
  from the transform origin — which is why it presents as intermittent. Phase
  D measures the hero after the travel ends, or divides the current scale back
  out (`rect.width / offsetWidth`, exactly 1 when nothing is mid-transform).

**And the trace window is now a declared value, not a comment.** The `≤900ms`
the draft named goes in `declare({traceWindow})` with its reasoning, so a
reader sees the guard's reach in the output header before its verdicts.

### 9.3 The full sweep

`just test` (pytest + `lint.py` + guards), `python3 lint.py --target .`,
`just audit-styleguide`, `git diff --check`. Guards bind 39890-39899; check
who owns the port first.

---

## 10 · Found while designing this — out of scope, worth filing

**The two findings this section opened with have both been fixed** by tasks
that landed after it was written, and they are recorded as resolved rather than
deleted, because a plan whose "known bugs" list has silently emptied gives the
next reader no way to tell fixed from forgotten:

- ~~`parse_ledger` cannot see combined entries.~~ **Fixed by `#301` (landed
  mentions) and `#315` (open heads).** `LEDGER_ENTRY` is now
  `^- \*\*(#\d+(?:/#\d+)*)\*\*` (`watch.py:1540`) and `parse_ledger` reads both
  sections combined-aware through `_open_ids`/`_landed_ids`
  (`watch.py:1648`). `lint.py`'s `LEDGER_ID` and `check_ledger_sections`
  widened in the same lockstep (`lint.py:43`, `:285`, `:382-392`). Verified:
  `- **#138/#156**`, `- **#250/#251**` and `- **#292/#293**` all parse today.
  §2.1 states the argument that replaced this one.
- ~~`TINT` and `SEED` have no `answers` entry.~~ **Fixed by `#302`
  (`cdb89df`).** `/answers` now carries `TINT.answers = 0.08` and
  `SEED.answers = 29` (`watch.py:3086`, `:3090`). Re-checked for this page: the
  proposed `TINT.tasks = -0.30` / `SEED.tasks = 13` still collide with nothing
  — tints are `0, 0.14, 0.08, -0.14, 0.22` and seeds `7, 23, 29, 41, 61`.
- The dispatch brief for that batch numbered the hovercard task `#213`; it is
  **`#282`**. `#213` is the landed forward-only origin-marker contract, which
  this design consumes rather than blocks. (Already corrected in `#281`'s
  ledger entry.)

**And two new findings, both measured, both out of this plan's scope and
both now filed:**

- **The landed reader sees only `/`-joined id spans — filed as `#331`.**
  `LEDGER_COMBINED_MENTION` (`watch.py:1570`) is `\*\*(#\d+(?:/#\d+)*)\*\*`.
  Grooming's compacted roll-up under `## Recently landed` also writes
  **space-joined** spans — `**#121 #123**`, `**#104 #77**`, `**#109 #116**`,
  `**#107 #108 #110**`, `**#102 #106**`, `**#141 #149**`, `**#132 #151 #154**`
  — and one `+`-joined, `**#157 + #222 + #223**`. Measured at `01df3b6`:
  **nineteen ids are in neither `parse_ledger` set** — `#77, #102, #104, #106,
  #107, #108, #109, #110, #116, #121, #123, #132, #141, #149, #151, #154, #157,
  #222, #223` — and **none of the nineteen was in a landed set at any of the
  295 ledger revisions**, so the history walk does not recover them: closing
  the gap moves the ever-landed total from **117 to 136**. It is a live
  under-count on the burndown's completion series, and it is why §3's blocker
  cross-check is three-way rather than two.

  Two things to carry into `#331` rather than rediscover. **The fix is not a
  third regex**: `#301` widened the landed reader, `#315` widened the open
  readers and `LEDGER_ID` together, and this is the same defect at a third
  door — one shared definition of "an ids-only bold span" that every reader
  consumes, pinned the way `test_ledger_entry_rule_has_exactly_one_copy`
  already pins two of them. And **`**#96 stage 1**` must stay inert** — a span
  is ids-only or it is prose; admitting trailing words would start reading
  section titles as ids, which is why `#96` is *not* in the nineteen and why
  it is the fixture the widening has to be red-proved against.
- **`status.json` has no structured way to say which task an agent is on —
  filed as `#332`.** This is what §2.3 needs for an honest `in progress`
  badge. Required change,
  stated exactly so the coordinator can land it in `file-formats.md`'s
  status.json table: add `current_task_ids` (array of ints, top level) and
  `task_ids` (array of ints, per agent) — *"the task ids this names, as
  integers; prose in `task` is not a substitute, because one sentence routinely
  names several ids in different states"*. Until it exists the page shows
  `in progress` from the ledger's own `· in progress` token only.

**One claim from an earlier draft of this review is withdrawn.** It said
`agents[].in_flight` was documented as prose and written as a bool, so the
agent glance read `doing: true`. **That is wrong and there is no such bug.**
`in_flight` holds prose in the live file and has held prose in every one of the
last forty revisions of `status.json`; the bool is `awaiting_result`, a
different key, and the two were conflated. The §2.3 argument does not depend on
it — see there for the reason `in_flight` cannot carry the badge, which is that
prose about the work names the wrong ids or none, measured.

---

## Increments

Each is one commit, ~15-20 minutes, independently verifiable. Stage by
explicit path. A commit touching `watch.py`'s page also touches
`watch-design.md` or `file-formats.md` (`just audit-styleguide`).

**The twelve-increment structure survives this review unchanged.** His rulings
moved work *inside* increments — sort becomes a control in Task 6, the badge
and its age box land in Tasks 5 and 8 — and moved the wide two-pane layout out
entirely into `#328`, which the proposal had never scheduled as an increment.
Nothing was added, merged or dropped. Only the checklists below changed.

### Task 1: Parse a ledger entry into a record

**Files:** Modify `watch.py`, `test_watch.py`, `file-formats.md`.

**Interfaces:** Produces `ledger_tasks(text)` → `[record]`, built on
`ledger_entries`; `task_priority(chain, title)`; `task_effort(token)`;
`task_blockers(entry)`.

- [ ] Write the failing parser tests: pytest cases 1-9 of §9.1.
- [ ] Run focused pytest; observe each red **for its own message** (case 9
      must fail as an IndexError, not as a missing attribute).
- [ ] Implement the parse: join the entry, lift a balanced annotation, split
      the chain, recognise fields by shape and never by position.
- [ ] Document the reader's grammar in `file-formats.md` under the existing
      `tasks.md` sections, `unknown` first-class throughout.
- [ ] Focused pytest green.

### Task 2: Expose the per-id git facts the walk already computes

**Files:** Modify `watch.py`, `test_watch.py`.

**Interfaces:** Produces `ledger_history(target)` →
`{id: {origin, first_commit, first_seen, landed_at, snapshot_title,
in_progress_since}}`. Consumes the existing `_LEDGER_SNAPS` memo
(`watch.py:1619`, currently `(open_ids, landed_ids, entry_origins)`), extended
to carry titles and the in-progress marker.

- [ ] Write failing tests: per-id arrival/landing/first-sight, a pruned id
      keeping a snapshot title, and case 15 (`ledger_series`' outputs
      unchanged).
- [ ] Observe red.
- [ ] Return the maps instead of discarding them; extend the memo tuple.
- [ ] **`snapshot_title` is not optional polish** — it is the only title the
      **87** `present: false` records have (§2.2). Assert in the test that the
      real ledger yields strictly more history ids than entry ids, so this
      cannot regress into a path with no exercised subject.
- [ ] **`in_progress_since`**: the commit time of the first snapshot in which
      that id's entry carried the `· in progress` token — the age the
      `Reported:` box renders (§2.3, case 19). One more derivation over text the
      walk already reads; no extra `git show`.
- [ ] Focused pytest green; confirm no additional `git show` per revision.

### Task 3: Merge them behind one function, and serve it

**Files:** Modify `watch.py`, `test_watch.py`, `file-formats.md`.

**Interfaces:** Produces `ledger_index(target)` (cached on HEAD, **the #294
swap point**) and GET `/tasksdata` (`?t=<id>` for one record).

- [ ] Write failing tests: cases 10-13, the payload ceiling, and health's
      three states.
- [ ] Observe red.
- [ ] Implement the merge, the health verdict, and the two response shapes;
      allowlist `/tasksdata`.
- [ ] Record the envelope and the swap point in `file-formats.md`.
- [ ] Focused pytest green.

### Task 4: Add the `/tasks` route (list shell only)

**Files:** Modify `watch.py`, `test_watch.py`, `watch-design.md`.

**Interfaces:** Produces the server allowlist entry, `routeOf`/`isInternal`
`tasks` branches, `TITLES.tasks`, `TITLE_ROUTE.tasks`, `crumbsFor` branch,
`TINT.tasks`, `SEED.tasks`, `buildTasks(d)`.

- [ ] Write the failing static route test (case 14) and a title/crumb test.
- [ ] Observe red.
- [ ] Add the route end to end; the view renders a bare list.
- [ ] Open `watch-design.md`'s `/tasks` section: routes, the URL contract, the
      dissolve signature.
- [ ] Focused pytest green.

### Task 5: The row, the facets, and the three nothings

**Files:** Modify `watch.py`, `test_watch.py`, `watch-design.md`.

**Interfaces:** Produces `taskRow(t)`, `taskFacets(t)`, `TASKS_NONE`, and the
`in progress` badge with its `Reported:` box.

- [ ] Write failing tests for the three empty states, the whole-or-absent
      facet rule, the accent/warn budget in the generated source, and case 18
      (the badge reads a structured source, never prose).
- [ ] Observe red.
- [ ] Implement the row (block link, two lines, priority as luminance) and the
      three nothings.
- [ ] **The badge says `in progress`** — no *"the loop says"*, no *"claim"*
      (his ruling 5) — and carries the `Reported: Xm Ys ago` box through the
      existing `agePair`/`.age[data-ct]` path (`watch.py:1441`, `:2756`), not a
      second formatter. It opens on **focus as well as hover** (§7's rule) and
      obeys `transitions.md` for its arrival and departure.
- [ ] **The row must lay out in its container, not against the page** — a row
      that only works inside a 72ch column forces `#328` to write a second one
      (§5.1).
- [ ] Document the row anatomy, the badge copy and *why* it is not hedged, the
      colour budget and its reasoning (amber = `#136`'s fact on a second file).
- [ ] Focused pytest green.

### Task 6: Search, filter, sort, and the URL

**Files:** Modify `watch.py`, `test_watch.py`, `watch-design.md`.

**Interfaces:** Produces `taskFilter(state)`, `taskSort`, the `q`/`f`/`s` URL
codec, the `aria-live` count line, `/` and Escape handling.

- [ ] Write failing tests for the codec round trip (including an unknown facet
      → ignored, never an empty list), case 17 (the `s` codec: unknown value
      dropped, default never written), and the labelled `no estimate` tail
      whose count is **derived at render**, not a literal.
- [ ] Observe red.
- [ ] **Sort is a THIRD `.sgroup` in the controls row** (his ruling 2:
      *"user configurable alongside filters"*), single-select, beside the two
      filter groups rather than in a menu. Three groups is the row's budget
      (§4.2).
- [ ] Implement the controls on the standing `.sgroup`; `replaceState`
      throttled with an immediate flush — sort replaces like the other two, so
      choosing a ranking adds no Back step.
- [ ] Document the history rule, that **sort is his** rather than the page's
      opinion, and the client-side ceiling with its record-count denominator.
- [ ] Focused pytest green.

### Task 7: Rows travel — guard phases B, C, L

**Files:** Modify `watch.py`; create `dev/capture/tasks.mjs`; modify
`justfile`, `watch-design.md`.

**Interfaces:** Produces `TASK_LIST`; consumes `snapshotCards`/`regroupCards`.

- [ ] Build the guard on `report.mjs` from its first line: `makeReporter()`,
      `declare({drives, traceWindow})` (it **throws** on a missing half),
      `present()` before anything is driven, `finish()` at the end. §9.2.
- [ ] Write phases B, C and L against the planted target, using `between()`
      copied verbatim from `reviewsplit.mjs:145` — **not** a count of distinct
      positions, which `transitions.md` now names as a mistake and five guards
      were converted away from.
- [ ] Derive and **print** each row's travel span, and assert it above a
      literal floor, so `between(...) >= 1` cannot pass on a 2px twitch.
- [ ] Run them red on the un-regrouped list; confirm B reports **zero**
      part-way frames and C reports a part-way frame under reduced motion.
- [ ] Route filtering and sorting through snapshot → mutate → regroup.
- [ ] Add `tasks` to `DEFAULT_GUARDS` (`justfile:135`) and to the justfile
      header's own-target notes, as `burndown` is.
- [ ] Guard green; record the motion contract in `transitions.md` (the list is
      the **fifth** user of one mechanism, not a new gesture).

### Task 8: The detail view

**Files:** Modify `watch.py`, `test_watch.py`, `watch-design.md`; extend
`dev/capture/tasks.mjs` (phases A, G, H).

**Interfaces:** Produces `buildTaskDetail(t, d)`, `taskFacts(t)`,
`taskBlockers(t, index)`.

- [ ] Write phases A, G, H and the unknown-id pytest.
- [ ] Observe red.
- [ ] Implement the fact grid (fixed key column), bidirectional blockers,
      the reflowed description, mentions, and the raw peek.
- [ ] **The blocker cross-check is three-way** (§3, case 8): landed / still
      open / known-to-history-but-unclassifiable / never named. Collapsing the
      third into *"not in this ledger"* is wrong on nineteen real ids today.
- [ ] **`buildTaskDetail(t, d)` stays container-agnostic** — `#328` calls it
      into a pane rather than a route, and that seam costs nothing here (§5.1).
- [ ] Document the detail contract and the `expand`-vs-navigate reasoning.
- [ ] Focused pytest + guard green.

### Task 9: List ↔ detail morph — phase D

**Files:** Modify `watch.py`, `transitions.md`; extend
`dev/capture/tasks.mjs`.

**Interfaces:** Consumes `flipDock`, `opts.fromRect`.

- [ ] Write phase D (hero never replaced; **at least one part-way frame** via
      `between()` with the span derived, printed and floored; no frame past the
      final rect — never a count of positions, per `transitions.md`).
- [ ] Measure the hero **after** the travel ends, or divide the current scale
      back out: the dissolve transforms its ancestor, so every rect under it
      reads ~3% small with the error growing from the transform origin.
- [ ] Run it red against navigation without `fromRect`.
- [ ] Wire both directions; fail to the plain dissolve when the destination
      row is absent.
- [ ] Record it in `transitions.md` beside the review-dock morph.
- [ ] Guard green.

### Task 10: His state survives any re-render — phase F

**Files:** Modify `watch.py`, `watch-design.md`; extend
`dev/capture/tasks.mjs`.

**Interfaces:** Produces `snapshotTaskFilter`/`restoreTaskFilter`;
`data-keep="task:<id>:raw"`.

- [ ] Write phase F, asserting first that the row nodes were replaced.
- [ ] Observe red (value lost, peek closed).
- [ ] Implement the snapshot pair; folds before filter before regroups.
- [ ] Add the surface to `watch-design.md`'s survival list with its statement
      of how it satisfies the rule.
- [ ] Guard green.

### Task 11: History, focus and keyboard — phases E, I, J, K

**Files:** Modify `watch.py`, `watch-design.md`; extend
`dev/capture/tasks.mjs`.

- [ ] Write phases E, I, J and K.
- [ ] Observe red (K against a deliberately accented priority).
- [ ] Implement focus-on-his-navigation-only, `/`, Escape, and the
      `history.length` discipline.
- [ ] Document the a11y contract.
- [ ] Guard green.

### Task 12: Land it

**Files:** all of the above, plus `.dreamwork/docs/doc-map.md`, `lint.py`,
`test_lint.py`.

- [ ] Add the `lint.py` priority WARN, reading the band rule from `watch.py`
      (case 16), red-first.
- [ ] Re-read the whole diff against `#281`'s ledger line; confirm nothing
      from `#282`/`#294` leaked in.
- [ ] `python3 -m pytest -q`, `python3 lint.py --target .`, the full guard
      sweep, `just audit-styleguide`, `git diff --check`.
- [ ] Commit, merge, deploy `watch.py`, verify with `deployed.py`.
- [ ] Coordinator updates `.dreamwork/tasks.md` and `status.json`; file §10's
      **three current** findings as tasks — the space-joined landed mentions,
      `in_flight`'s bool-vs-prose contract break, and the `status.json`
      structured task-id field. The section's two original findings are already
      fixed (`#301`/`#315`, `#302`) and the id correction is recorded (not a
      task).

---

## His rulings — answered 2026-07-27 21:47, and binding

The seven open questions this document was written to ask have been answered.
They are recorded here as **decisions**, not as recommendations, because a
plan that still argues its own refuted option is a plan that gets built
wrong. Where his answer overrode the recommendation, the reasoning above has
been amended to match — §1.2, §4.2, §5.1 and §3 each carry his call now, not
the proposal's.

1. **A wider two-pane list-plus-detail triage layout — APPROVED, at its own
   route.** *"yes, but at `/tasks2`, and keep a simpler one-column variant at
   `/tasks`."* So the recommendation (*no, for v1*) is **overruled**, and the
   proposal's argument against a second width exception is not the reason to
   skip it — it is the reason `/tasks` stays one column while the wide layout
   gets its own address. `/tasks2` is **`#328`** and is out of this plan's
   scope; what this plan owes it is a clean seam and no second parser (§5.1).

2. **Default sort: priority, then newest id — accepted, "but user
   configurable alongside filters."** So sort is a **control**, not a
   constant, and it lives in the controls row with the filters. §1.2 and §4.2
   carry the consequences; the URL key was already `s`, which is what makes
   this a UI addition rather than a contract change.

3. **Default filter: open only — as proposed**, with the landed count visible
   in the count line and one click away.

4. **`/tasks?t=281` is the canonical detail URL — as proposed.** `#282` may
   hardcode it.

5. **Show the in-flight signal, but say "in progress" — the hedge is
   rejected.** No *"this is a claim"* label; the honesty is carried instead by
   a hover box reading **"Reported: Xm Ys ago"**.

   **Why his version is better, stated because it should shape the rest of
   the copy:** freshness is a *fact*, where "the loop's claim" is a
   *disclaimer*. A disclaimer admits the page might be wrong and leaves the
   reader no way to tell; a measured age makes staleness **legible** — a
   signal reported four seconds ago and one reported forty minutes ago read
   differently, and only the measurement can say which he is looking at.
   Anywhere else in this document that hedges where it could instead show a
   measurement is the same defect and is to be fixed the same way.

6. **A per-row write affordance is NOT approved and NOT in scope.** He asked
   what it would mean rather than answering it, and it has been re-asked as
   its own question. Nothing in this plan may assume it: §Global constraints'
   read-only rule stands unchanged, and no increment adds a POST seam.

7. **File the findings — as proposed.** Both original findings have since
   been fixed by other tasks (`#301`/`#315` and `#302`); §10 now carries what
   replaced them.

---

--- SUMMARY ---

- **Route.** `/tasks` is the list; **`/tasks?t=<id>`** is the canonical task
  detail — a query param, so the server's exact-match route allowlist stays
  exact and `#133`'s prefix wraps it for free. Search/filter/sort live in
  `q`/`f`/`s` and use `replaceState`, so Back never walks his own typing;
  only route changes push.
- **Data.** One new deep module in three parts: `ledger_tasks(text)` (pure
  entry-level parse on `ledger_entries`' grammar — whose *reason* changed after
  `#315` widened `LEDGER_ENTRY`: the argument is now that `ENTRY_HEAD` is wider
  and an entry with a non-id head would vanish, not that combined heads are
  missed), `ledger_history(target)` (the per-id arrival/landing/first-sight
  facts the existing burndown walk already computes and discards, plus the
  snapshot title and the in-progress marker's age), and `ledger_index(target)`
  — cached on HEAD and **the single swap point for `#294`**. Records ride a
  route-scoped `/tasksdata`, not `/data.json`, which measures **456,842 bytes**
  every two seconds.
- **Honesty, re-measured at `16ef2e2`.** Every field is parsed, derived or
  **unknown**, and unknown renders as unknown. Coverage is a measurement with a
  date, not a constant — 148 entries (106 open, 42 landed), priority 106/106,
  effort 64/106 numeric, origin marker 59/106, blockers 21/106 — and the
  figures the first draft carried had all aged out inside a day.
  **`present: false` is 87, not 0**: 36% of the 244 ids this ledger has ever
  named have no entry, because grooming compacts Recently-landed into prose
  roll-ups. **Owner is not detectable** and the page says so. **In progress
  is shown and says "in progress"** (his ruling), evidenced only by a
  structured source, with the honesty carried by `Reported: Xm Ys ago` through
  the existing `agePair` formatter. The blocker cross-check is **three-way**,
  because nineteen genuinely-landed ids are currently in neither reader set.
- **Design.** `/tasks` is one 72ch column **by his ruling**, with the wide
  two-pane triage layout **approved at `/tasks2` (`#328`)** — so the row, the
  detail builder and `ledger_index` are the seam it composes, and it inherits
  `/review`'s post-`#305` split idiom rather than authoring a second one. A
  two-line block-link row whose every field is whole or absent (no truncated
  preview — `#106`); priority as luminance, not colour; `--accent` spent on
  exactly one thing (the `in progress` rail) and `--warn` on exactly one (a
  ledger the reader cannot see, `#136`'s fact on a second file); three
  distinguishable kinds of nothing. Sort is a **third `.sgroup` beside the
  filters**, his to set.
- **Motion.** No new mechanism: filtering and sorting are `#104`'s regroup
  over a **fifth** keyed list (`TASK_LIST`, beside `QA_LIST`, `ANSWER_LIST`,
  `GIT_LIST` and `REVIEW_LIST`), list↔detail is the review dock's lifted-hero
  morph in both directions failing to the plain dissolve, and the raw-entry
  peek is the section fold's pieces. `/tasks` gets the sixth dissolve
  signature of a now-complete set (`#302` closed the `/answers` gap). Reduced
  motion changes timing, never function.
- **Verification.** 21 pytest checks and 12 browser-guard phases, each with the
  bug named that will be reintroduced to see it red. The guard is written on
  **`dev/capture/report.mjs`** (`#192`, which post-dates the draft): the crash
  sentinel, `present()` absence-first, no count offered at all, and a
  `declare({drives, traceWindow})` that throws on a missing half. It **builds
  its own git target** because the shared fixture is not a repository and holds
  no ledger, and the fixture is deliberately not seeded. The motion phases are
  rewritten in `transitions.md`'s **current** form — one part-way frame via
  `between()` with a derived-and-printed span above a literal floor, never an
  absolute count of distinct positions, which is the exact idiom the draft
  specified and five guards have since been converted away from.
- **Twelve increments**, unchanged in number and boundary by this review, each
  independently committable, ending in lint, docs, deploy and verification.
- **His seven rulings are recorded as decisions, not recommendations** — the
  two-pane layout **approved at `/tasks2`**, sort **user-configurable**, filter
  open-only, `?t=281` canonical, the in-flight signal saying **"in progress"**
  with a measured freshness box instead of a hedge, a per-row write affordance
  **not approved and not in scope**, and the findings filed. Three of those
  overrode this proposal's own recommendation, and §§1.2, 3, 4.2, 5.1 and 5.4
  now state his call rather than arguing against it.
- **§10 is current.** Its two original findings are fixed (`#301`/`#315`,
  `#302`); **two** measured replacements stand and both are filed — the landed
  reader seeing only `/`-joined id spans, so nineteen landed ids are in neither
  set and history does not recover them (`#331`), and `status.json` lacking any
  structured task-id field (`#332`). A third claim, that `in_flight` was
  written as a bool, was **withdrawn on challenge**: it is prose, and always
  was; `awaiting_result` is the bool. The §2.3 argument stands on a measured
  replacement — prose about the work names the wrong ids or none.
