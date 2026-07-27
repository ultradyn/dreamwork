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
  new authority surface and is deliberately out of scope (open question 6).
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
  `parsed.path in (…)` membership test (watch.py ~7292). A path segment turns
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
  (which `#218` names in its own entry). It returns them instead, memoised on
  the same immutable `(rev, path)` snapshot key, and additionally keeps each
  entry's **title** per snapshot so a pruned task still has one. Cost: one
  extra dict per revision, ~1MB at today's 139 ledger commits, no extra
  `git show`.
- `ledger_index` is the merge, cached on HEAD exactly as `ledger_stats` is,
  and it is **the swap point** (§8).

**The grammar is `ledger_entries`, not a copy of it.** That function is pinned
byte-identical between `watch.py` and `lint.py` by a test, and it is the only
reader that gets combined entries right. Building on `LEDGER_ENTRY`
(`^- \*\*#(\d+)\*\*`) instead would silently drop `- **#250/#251**`,
`- **#292/#293**` and `- **#138/#156**` — which is a bug that exists today in
`parse_ledger` and is filed rather than fixed here (§10).

### 2.2 The record, field by field

Coverage figures are measured against today's ledger (104 open entries, 17
landed, 121 total).

| field | source | rule | today |
|---|---|---|---|
| `ids` | leading bold token, via `ledger_entries` | every numeric id in it; a `#N` in the body is a cross-reference and numbers nothing | 121/121 |
| `id` | first id in `ids` | the display id; all of `ids` address the record | 121/121 |
| `section` | which `##` heading it sits under | `open` \| `landed`; an entry before any heading is `unknown` | 121/121 |
| `title` | after the em dash, up to the first ` · ` | never truncated; if there is no ` · ` the whole remainder is the title | 121/121 |
| `annotation` | a leading balanced `[…]` before the title | lifted out so the title is the title; **unbalanced → no annotation** and the text stays in the title (fail toward keeping his words) | 9/121 |
| `priority_raw` | a chain token matching `P[0-3](/P[0-3])*`, **or** a bolded `**P2**` adjacent to the title | rendered verbatim, compounds included | 103/104 open (the 104th is #99's bolded form) |
| `priority_band` | derived | the first recognised band in a compound (`P0/P1` → P0 — the entry is claiming at least P0). **Absent → P2**, the same middle-band rule as `questions.md`, and `priority_raw: null` so the page can say *unmarked* rather than implying an explicit P2 | all |
| `kind` | the chain token after the priority | free prose (`idea`, `Web UI bug`, `storage/tooling migration`) — recorded, never normalised into a closed set the ledger does not have | ~100/104 |
| `effort_raw` | a chain token that reads as a size | verbatim (`20m`, `several increments`, `2 parts`, `later`) | 65/104 parse to minutes; the rest keep prose |
| `effort_min` | derived from `effort_raw` | only `^\d+\s*(m\|min\|h\|hr)$`. **`4-5 increments` yields no number** — a digit-anywhere regex would report 4 minutes | 65/104 |
| `origin` | `entry_origins`' rule, verbatim | exactly one marker in `human`/`loop` is a claim; none, several, or wrong case → `unknown` | 53/104 open |
| `origin_first_sight` | git | the arrival classification (`#216`); first sight is final and never revisited | history-wide |
| `arrival_raw` | a `**human …**` / `**loop …**` stamp in the chain | verbatim, including the channel (`via watch \`add-idea\` 14:37`) | 59/104 |
| `arrival_when` | parsed out of `arrival_raw` | `YYYY-MM-DD` and/or `HH:MM`. **A time with no date stays a time** — no date is invented from the file's context | subset of the above |
| `first_commit` / `first_seen` | git | the first committed snapshot naming the id. **The only trustworthy filed-date** | history-wide |
| `landed_at` | git | the first snapshot naming the id under `## Recently landed`. Survives grooming, which the text claim does not | 82 ids |
| `landed_claim` | `landed <date>` in the entry text | the ledger's own claim. Shown **only** when git is unavailable, labelled as the ledger's claim | 17/17 landed |
| `sha` | a trailing `` `<7-12 hex>` `` | the landing commit the entry names; plain text, **not a link** (`#157`'s rule: a path/rev from an old commit may not resolve, and a link that 404s promises something) | 15/17 landed |
| `blocked_on` | `blocked on …` up to the next ` · ` | every `#N` in that span (`blocked on #264 design and relevant #263 cutover decisions` → `[264, 263]`) | 19/104 |
| `blocked_note` | the same span, verbatim | because some blockers are prose, not ids (`blocked on user-event model #263`) | 19/104 |
| `refs` | every other `#N` in the entry | cross-references, for the detail view's "mentions" | all |
| `description` | the remaining chain tokens | reflowed through `mdB`; **the whole thing, never a preview** | all |
| `raw` | the entry verbatim | **only on the single-record response**, never in the list payload (§4.3) | all |
| `present` | `false` for a git-only (pruned) id | with `title` from the last snapshot that held it | 0 today |

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

  `agents[].in_flight` does not rescue it: `file-formats.md:494` documents it
  as *"one line: what it is doing right now"*, and the live file writes
  `"in_flight": true` — a bool, naming no id at all.

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
| `landed` | git says the id first appeared under `## Recently landed`, or the entry sits there now | dim end of the ramp; carries the date and the sha |
| `landed · entry pruned` | git says landed; no entry in the current file | as above, title from the last snapshot |
| `unknown` | leading token parses no id, or no section can be determined | rendered **as unknown and still listed** — the entry exists, so it is reachable |

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
  `LEDGER_COMBINED_MENTION` (`watch.py:6340`), an ids-only bold span joined by
  `/`. The landed section's compacted roll-up also writes **space-joined**
  spans — `**#121 #123**`, `**#104 #77**`, `**#109 #116**`,
  `**#107 #108 #110**`, `**#102 #106**` — and `**#96 stage 1**`, none of which
  match. Measured on today's file: **#77, #96, #102, #104, #106, #107, #108,
  #109, #110, #116, #121 and #123 are in neither the open set nor the landed
  set**, though every one of them landed and is named in the file.
  So `blocked on #106` must **not** render `not in this ledger` — that is
  precisely the wrong claim this rule exists to prevent, and it would be wrong
  on twelve real ids. The cross-check is three-way:
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
route-scoped payload. 121 records is a sub-millisecond scan; a server round
trip per keystroke would add a new endpoint shape, break the deep-link model
(the URL would no longer be sufficient state), and buy nothing measurable.

**And it does not scale forever, so the ceiling is named rather than
discovered:** at ~600 entries or a `/tasksdata` list body over ~512KB,
whichever comes first, search moves behind `#294`'s query API. The
implementation asserts the current size in a pytest so the ceiling arrives as
a red light rather than as a slow page. (Today's ledger is 103KB of Markdown;
the list payload measures **139KB**, see §4.3.)

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
  `38 of 104 open · 17 landed`. It is an `aria-live="polite"` region, which is
  the screen-reader equivalent of watching rows travel (§7).

### 4.3 The payload

New GET `/tasksdata`, allowlisted beside `/filedata`:

- `/tasksdata` → `{generated, health, note, history_complete, tasks:[…]}`,
  **without `raw`**. Measured on today's ledger: **139KB** without it,
  **226KB** with — `raw` is 63% of the body for a field only the detail view
  reads.
- `/tasksdata?t=281` → `{task: {…, raw}}` or `{task: null}`.

**It is a route-scoped fetch, not a `/data.json` field.** `/data.json` is
already 374KB (measured) and is re-fetched every ~2s on every open window;
adding the parsed ledger to it would put 139KB of task text on the wire every
two seconds for the benefit of one route. `/filedata` is the standing precedent
for exactly this. The client caches it and invalidates on a changed `/mtime`,
so liveness is unchanged and the cost is paid only where it buys something.

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
| `no match` | the ledger is fine, the filter matches nothing | `nothing matches "xyz" · 104 tasks in the ledger` and a one-click clear. **Never collapsed into "no tasks"** |

---

## 6 · Motion

Per `transitions.md`. Nothing below is a new mechanism.

### 6.1 Route entry and exit

The dream dissolve, with `TINT.tasks` and `SEED.tasks` entries of its own
(`-0.30` / `13` — distinct from dashboard 0, questions .14, file -.14, review
.22). A destination without its own signature silently shares another's,
which is a real gap today for `/answers` (§10).

### 6.2 Rows arriving, departing and reordering

**This is `#104`'s regroup over a third list, and it must be the same
`snapshotCards`/`regroupCards` pair** — a second implementation of "one
leaves, its neighbours travel" is two things to keep true.

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

The detail's raw-entry peek uses `foldDetailsLocal` — height travel +
`revealBody` arrival + `dreamAway` departure, the section-fold pieces, with
`box-sizing:border-box` while the height animates. It does **not** get a
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

- **Semantics.** `<ol>` labelled `open tasks · 38 of 104`; one `<li>` per
  record; the row is a block `<a href="/tasks?t=281">` whose accessible name is
  the whole row. Facet tokens carry visually-hidden prefixes only where the
  bare value is ambiguous (`filed 2026-07-26`, `origin human`).
- **The count line is `aria-live="polite"`.** A sighted reader watches rows
  travel; a screen-reader user hears `38 of 104 open`. Without it, filtering
  is a silent event, which is the same class of failure as a fold that hides
  something in flight.
- **Keyboard.** Rows are links, so Tab/Enter/middle-click/new-tab work with no
  JS (modified clicks already fall through `isInternal`). `/` focuses the
  search box and is **ignored inside text fields** — the same rule the shader
  hotkey already obeys. `Escape` in the search box clears the filter (and
  replaces the URL). No modal keymap is invented.
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
| 1 | a combined entry yields ONE record addressable by either id | building on `LEDGER_ENTRY` instead of `ledger_entries` → the entry vanishes |
| 2 | a `#N` in a body numbers nothing | `ENTRY_ID.findall(whole_entry)` |
| 3 | origin fails closed: two markers → unknown; `**Human**` → unknown | taking `marks[0]` without the count/vocabulary test |
| 4 | a hard-wrapped metadata chain parses (`origin:` ending a line) | parsing per physical line instead of joining the entry |
| 5 | `P0/P1` → band P0, raw preserved; absent → band P2 with `priority_raw: null`; `**P2**`-before-title is found; `P4` → no band, raw kept | `int(tok[1])`, or defaulting `priority_raw` to `"P2"` |
| 6 | `20m` → 20; `4-5 increments` → **no** minutes, raw kept | a digits-anywhere regex (reports 4) |
| 7 | `blocked on #264 design and relevant #263 cutover` → `[264, 263]` + verbatim note | anchoring the pattern at end-of-token |
| 8 | a blocker in the landed set surfaces `blocker_landed`; an absent blocker surfaces `blocker_missing` | dropping the cross-check → blocked forever / a wrong claim |
| 9 | an entry whose leading token has no digits yields `ids: []`, state unknown, **and is still listed** | `ids[0]` → IndexError → the whole route 500s |
| 10 | landing date comes from git; with no repository, the text claim is shown **labelled** | reading only one of the two → a pruned entry has no date, or a non-checkout shows nothing |
| 11 | a git-only (pruned) id appears with `present: false` and a snapshot title | building the list from the file alone |
| 12 | `/tasksdata` omits `raw`, and the list body is under the stated ceiling | including `raw` |
| 13 | `/tasksdata?t=9999` → 200 `{task: null}`; `?t=abc` likewise | returning 404 |
| 14 | `/tasks` and `/tasks?t=1` both serve the shell (allowlist) | leaving the allowlist unchanged |
| 15 | `ledger_series`' existing outputs are byte-identical after the refactor | changing a bucket boundary while exposing the maps |
| 16 | `lint.py` WARNs on a token that reads as a priority and parses to no band, reading the band rule **from watch.py** | giving the linter its own copy of the rule (the exact drift `#197` paid for) |

### 9.2 Browser guard — `dev/capture/tasks.mjs`

**It builds its own git target and takes an ephemeral port.**
`dev/capture/fixture` is not a repository and holds no `tasks.md`, so every
check against the shared server would pass against nothing — the trap
`burndown.mjs`, `provenance.mjs`, `gitrow.mjs` and `dashboard.mjs` each name.
The fixture is **not** extended: seeding it can make a *neighbouring* guard
vacuous without making it red, which is the worse failure. History is planted,
so the numbers are known rather than read off the page and compared to itself.
It asserts its subject **exists** before driving it, so absence costs one line
instead of a 120s timeout.

| phase | asserts | red by |
|---|---|---|
| A route | direct load of `/tasks?t=281` renders the detail, the title reads `task #281`, the crumb is `← tasks` | routing param-less → the list renders |
| B filter motion | on a real typed keystroke: every surviving row visits **many distinct intermediate positions**, every departing row leaves a ghost at its own rect, and **no frame goes past the final position**. Trace bounded to the interaction (≤900ms) | rebuilding via `innerHTML` with no regroup → exactly 2 distinct positions |
| C reduced motion | same filter: ≤2 distinct positions, **and** the same final row set, the same count line, focus still moved | skipping the RM branch (motion appears) or letting RM skip the filter (function lost) |
| D morph | clicking a row: the hero node was **never replaced** across the window, travelled many positions, and no frame went past its final rect | navigating without `fromRect` |
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

### 9.3 The full sweep

`just test` (pytest + `lint.py` + guards), `python3 lint.py --target .`,
`just audit-styleguide`, `git diff --check`. Guards bind 39890-39899; check
who owns the port first.

---

## 10 · Found while designing this — out of scope, worth filing

- **`parse_ledger` cannot see combined entries.** `LEDGER_ENTRY`
  (`^- \*\*#(\d+)\*\*`) requires `**` immediately after the digits, so
  `- **#138/#156**`, `- **#250/#251**` and `- **#292/#293**` match nothing.
  Measured: `ledger_entries` finds 123 ids where `parse_ledger` finds 118, and
  the burndown's arrival, completion and open-level series are wrong by that
  much. `entry_origins` (built on `ledger_entries`) is already right, so the
  two readers disagree about the same file.
- **`TINT` and `SEED` have no `answers` entry**, so `/answers` silently
  inherits the dashboard's atmosphere (`TINT[name] || 0`) while
  `transitions.md` states that each destination has its own turbulence seed
  and tint.
- The dispatch brief for this batch numbered the hovercard task `#213`; it is
  **`#282`**. `#213` is the landed forward-only origin-marker contract, which
  this design consumes rather than blocks.

---

## Increments

Each is one commit, ~15-20 minutes, independently verifiable. Stage by
explicit path. A commit touching `watch.py`'s page also touches
`watch-design.md` or `file-formats.md` (`just audit-styleguide`).

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
`{id: {origin, first_commit, first_seen, landed_at, snapshot_title}}`.
Consumes the existing `_LEDGER_SNAPS` memo, extended to carry titles.

- [ ] Write failing tests: per-id arrival/landing/first-sight, a pruned id
      keeping a snapshot title, and case 15 (`ledger_series`' outputs
      unchanged).
- [ ] Observe red.
- [ ] Return the maps instead of discarding them; extend the memo tuple.
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

**Interfaces:** Produces `taskRow(t)`, `taskFacets(t)`, `TASKS_NONE`.

- [ ] Write failing tests for the three empty states, the whole-or-absent
      facet rule, and the accent/warn budget in the generated source.
- [ ] Observe red.
- [ ] Implement the row (block link, two lines, priority as luminance) and the
      three nothings.
- [ ] Document the row anatomy, the colour budget and its reasoning
      (amber = `#136`'s fact on a second file).
- [ ] Focused pytest green.

### Task 6: Search, filter, sort, and the URL

**Files:** Modify `watch.py`, `test_watch.py`, `watch-design.md`.

**Interfaces:** Produces `taskFilter(state)`, `taskSort`, the `q`/`f`/`s` URL
codec, the `aria-live` count line, `/` and Escape handling.

- [ ] Write failing tests for the codec round trip (including an unknown facet
      → ignored, never an empty list) and the labelled `no estimate` tail.
- [ ] Observe red.
- [ ] Implement the controls on the standing `.sgroup`; `replaceState`
      throttled with an immediate flush.
- [ ] Document the history rule and the client-side ceiling.
- [ ] Focused pytest green.

### Task 7: Rows travel — guard phases B, C, L

**Files:** Modify `watch.py`; create `dev/capture/tasks.mjs`; modify
`justfile`, `watch-design.md`.

**Interfaces:** Produces `TASK_LIST`; consumes `snapshotCards`/`regroupCards`.

- [ ] Write phases B, C and L against the planted target.
- [ ] Run them red on the un-regrouped list; confirm B reports exactly 2
      distinct positions and C reports motion under reduced motion.
- [ ] Route filtering and sorting through snapshot → mutate → regroup.
- [ ] Add `tasks` to `GUARDS` and to the justfile header's own-target notes.
- [ ] Guard green; record the motion contract in `transitions.md` (the list is
      a third user of one mechanism, not a new gesture).

### Task 8: The detail view

**Files:** Modify `watch.py`, `test_watch.py`, `watch-design.md`; extend
`dev/capture/tasks.mjs` (phases A, G, H).

**Interfaces:** Produces `buildTaskDetail(t, d)`, `taskFacts(t)`,
`taskBlockers(t, index)`.

- [ ] Write phases A, G, H and the unknown-id pytest.
- [ ] Observe red.
- [ ] Implement the fact grid (fixed key column), bidirectional blockers,
      the reflowed description, mentions, and the raw peek.
- [ ] Document the detail contract and the `expand`-vs-navigate reasoning.
- [ ] Focused pytest + guard green.

### Task 9: List ↔ detail morph — phase D

**Files:** Modify `watch.py`, `transitions.md`; extend
`dev/capture/tasks.mjs`.

**Interfaces:** Consumes `flipDock`, `opts.fromRect`.

- [ ] Write phase D (hero never replaced; many positions; no frame past the
      final rect).
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
- [ ] Coordinator updates `.dreamwork/tasks.md` and `status.json`; file the
      two §10 bugs as tasks (the third finding is a brief correction, not a
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
  entry-level parse, built on the pinned `ledger_entries` grammar),
  `ledger_history(target)` (the per-id arrival/landing/first-sight facts the
  existing burndown walk already computes and discards), and
  `ledger_index(target)` — cached on HEAD and **the single swap point for
  `#294`**. Records ride a route-scoped `/tasksdata`, not `/data.json`, which
  is already 374KB every two seconds.
- **Honesty.** Every field is parsed, derived or **unknown**, and unknown
  renders as unknown. Coverage is measured, not assumed (priority 103/104,
  effort 65/104, origin marker 53/104, blockers 19/104). **Owner and
  in-progress are not detectable from the ledger** and the page says so; the
  only in-flight signal is `status.json`'s claim, labelled as a claim.
  `blocked on #216 · which landed` and `blocked on #999 · not in this ledger`
  are separate, stated states — the page never silently unblocks anything.
- **Design.** One 72ch column; a two-line block-link row whose every field is
  whole or absent (no truncated preview — `#106`); priority as luminance, not
  colour; `--accent` spent on exactly one thing (the loop's live claim) and
  `--warn` on exactly one (a ledger the reader cannot see, which is `#136`'s
  fact on a second file); three distinguishable kinds of nothing.
- **Motion.** No new mechanism: filtering and sorting are `#104`'s regroup
  over a third keyed list (`TASK_LIST`), list↔detail is the review dock's
  lifted-hero morph in both directions failing to the plain dissolve, and the
  raw-entry peek is the section fold's pieces. Reduced motion changes timing,
  never function.
- **Verification.** 16 pytest checks and 12 browser-guard phases, each with
  the bug named that will be reintroduced to see it red; the guard **builds
  its own git target** because the shared fixture is not a repository and
  holds no ledger, and the shared fixture is deliberately not seeded.
- **Twelve increments**, each independently committable, ending in lint,
  docs, deploy and verification.
- **Seven open questions**, each with a recommendation: the wide two-pane
  layout (rec no), default sort (rec priority), default filter (rec open
  only), the URL shape (rec `?t=`), showing the loop's claim (rec yes,
  labelled), a future row-level `do now` (rec follow-up), and filing the three
  bugs found on the way (rec yes — `parse_ledger` is blind to combined
  entries, so the burndown is currently under-counting).
