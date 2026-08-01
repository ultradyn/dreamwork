# Persistent user settings — schema + seam + frontend exposure (#571)

**Design only — no code authorised.** No `watch.py`, no `ledger_store.py`,
no `lint.py`, no `file-formats.md`, no justfile, no ledger. This doc + a
doc-map row are the deliverable; he rules, then a later split builds.

## His words (journal ord=67, receipt 09a8897b, filed #571 — verbatim)

> Add persistent user settings in the database, probably just store it as
> jsonb if you can. indexed by userid, ofc. this will give us flexibility
> to then design and build a principled settings system for the frontend,
> including tags for the settings, descriptions, support for enums etc —
> actually, just check `~/src/refs/amr-ui/` for a good example of what I'm
> thinking of, structurally.

The last clause is load-bearing: amr-ui is the **structural** example
(tags, descriptions, enums), and the design must say exactly what maps
and what does not. The "jsonb / indexed by userid" sketch is his
starting point, not a ruling — the doc grounds it in this repo's reality
and surfaces the forks (the IGC below).

## The reference, investigated not assumed — `~/src/refs/amr-ui/`

amr-ui's settings live in `src/lib/settings.ts`. The **single source of
truth is a code-declared registry** — `SETTINGS`, a `Record<string,
Schema>` — where each entry carries its `kind`, `default`, `label`,
`category` (the "tag"), `description`, and (for enums) the closed
`values` set plus optional display `labels` and a `control` hint
(`radio` vs `select`). Four kinds: `boolean`, `enum`, `number`, `string`
(`settings.ts:62`–`90`). A `hidden` field of subtype `advanced` | `dev` |
`debug` | `lowLevel` gates advanced rows, and **any `hidden` entry must
declare a `description`** (the `Visibility` type enforces it,
`settings.ts:49`). The store holds **only non-default overrides**:
`amaroo:settings:values` is `Partial<SettingsValues>` — a key absent from
the store reads its registry default (`settings.ts:648`–`770`). Reads
`getSetting`, writes `setSetting`, a `validate()` per kind, a
per-key subscriber map + `BroadcastChannel`/`storage` listener for
cross-tab sync, a `SCHEMA_VERSION` + a migration ladder, and a
`visibleSettingsByCategory()` that the settings page iterates to render
sections generically (`settings.ts:828`). The settings page
(`pages/settings/SettingsPage.tsx`) iterates the registry grouped by
`category`, renders one `SettingRow` per key, and a per-subtype reveal
popover for hidden rows.

### What maps to this repo — and the one thing that does not

**Maps directly (the structural ideas he named):**

- **A code-declared registry as single source of truth** — keys + kinds +
  defaults + `category` (tag) + `description` + enum closed-sets declared
  in code, with the store holding **only non-default overrides**. This is
  amr-ui's central design, and it is *also* this repo's existing posture
  shape: `.dreamwork/posture` is a code-declared closed set (the axes and
  their stop-tuples live in `lint.py`), and the file holds only overrides
  (`file-formats.md:1124`, `orchestrator-posture.md`). The registry model
  is a **generalisation of posture to arbitrary keys**, not a new idea.
- **The four kinds** (boolean / enum / number / string) and the per-kind
  `validate()` — directly portable.
- **The `category`/`description`/`hidden`/`labels`/`control` metadata** —
  exactly the "tags, descriptions, enum support" he named.
- **A generic settings page that iterates the registry** rather than
  hand-built controls — the `visibleSettingsByCategory()` pattern.

**Does NOT map (the decisive difference, and #228 already ruled it):**

- **amr-ui's store is `localStorage` — browser-local.** This repo's
  standing ruling (#228, his words at 12:49, `tasks.md.deprecated:2404`)
  is that settings **"persist and stay identical across tabs and separate
  browsers"** and **"never localStorage"** (`#227`, `tasks.md.deprecated:2413`).
  localStorage is per-browser; it does not cross browsers and it does not
  reach a running loop. amr-ui's cross-tab `BroadcastChannel`/`storage`
  sync is intra-browser only. So amr-ui's **registry model maps; its
  storage layer does not** — this repo's settings live **server-side,
  gitignored machine-local**, and converge through the existing `/data.json`
  + `/mtime` poll (the same channel tint, run-mode, and posture use). The
  IGC below turns on this.

## Two load-bearing facts, measured read-only

### 1 · The store is SQLite, machine-local per clone — "jsonb" is TEXT+JSON here

The ledger store is stdlib `sqlite3` (`ledger_store.py:31`), at
`.dreamwork/ledger.sqlite3`, **gitignored as machine-local** (C1 —
`.gitignore`: *"the ledger store is machine-local (C1 — the same trust
boundary as the journal)"*; confirmed by #264's finding that every
load-bearing store is machine-local per clone). It is WAL + `synchronous=FULL`
(`ledger_store.py:344`–`352`), with a `meta` table holding
`schema_version` and a forward-only migration ladder
(`MIGRATIONS`, `dreamwork_db/migrate.py:28`). **SQLite has no native jsonb type**
— "jsonb" in his sketch means **TEXT + JSON validation in code** (Python's
`json.loads` on read, and `CHECK` or app-level validation on write). A
second sqlite store — `.dreamwork/user-events.sqlite3` — already lives
co-resident under `.dreamwork/`, gitignored, WAL, with the same pragma
discipline (`user_events/sqlite.py:1`). So "a new table in the ledger
store" and "a separate settings store" are both shapes this repo already
runs; the IGC compares them.

### 2 · v1 is single-user — "indexed by userid" is forward-looking, not load-bearing now

The whole dashboard is single-user today (one human, one machine, one
clone per project). There is no users table, no auth identity, no
multi-tenant boundary — `#275`/`#276` hub auth is the standing question,
not a landed fact. So `userid` in v1 is a **forward-looking column with a
single constant value** (e.g. `userid = 'local'` or `0`), not a real key
that discriminates rows. Designing it in now is cheap (one column); making
it load-bearing now would be premature (no second user exists to key on).
The doc says this plainly.

### 3 · The read/write seam already exists — `watched_mtime` + the write-route table

Everything in `collect()` rides one invalidation signal: `watched_mtime`
walks all of `.dreamwork/` (respecting `WATCHED_MTIME_IGNORED`,
`watch.py:4164`), and the client polls `/mtime`, so any file under
`.dreamwork/` that changes reaches every open dashboard on the next tick
with **no new channel** (`watch.py:6077`). Writes go through
`WRITE_ROUTE_HANDLERS` (`watch.py:6077`) — a single dispatch table that
E2 derives its route coverage from, where the journal commit/receipt
(E2Shadow) runs before dispatch. The simplest precedent is
`watch-tint`/`run-mode`/`posture`: a gitignored `.dreamwork/` file, a
`read_X`/`write_X` pair with closed-set validation and silent-fallback
on a bad value, one field in `collect()`, and one write route
(`read_tint`/`write_tint` `watch.py:4264`; `resolve_posture`/`write_posture`
`watch.py:4394`; `_handle_posture` `watch.py:5863`). A settings seam is
the same shape, generalised to N keys through a registry.

## The IGC — store shape, metadata location, posture relationship

Method: `igc-method.md`. Binary goals, decisive errors, one survivor or a
real fork. The **ideas are the store-shape + metadata-location
combinations**; the read seam and the frontend surface are settled by the
goals, not forked independently.

### Context

A single developer steers an autonomous loop through a machine-local,
gitignored dashboard. He wants a **principled settings system** (tags,
descriptions, enums, defaults) that persists server-side and converges
across tabs/browsers (#228), so that #573 (ask-me composer toggle), a
future #570 autoexpand-persistence setting, and #295's dither toggle (gfx
section) all read one shape instead of each inventing its own
`.dreamwork/` file. The settings must reach a running loop and every open
page; they must not be browser-local (localStorage fails this); and they
must not duplicate the posture concept (posture is already
code-declared-closed-set-with-file-override).

### Goals (binary; each can refute alone)

- **G1 — converges across tabs AND browsers** (the #228 ruling). A setting
  changed in one tab/browser reaches every other within a tick. localStorage
  fails this (per-browser); a gitignored `.dreamwork/` store passes it
  (rides `/data.json` + `/mtime`).
- **G2 — reaches a running loop** (survives a process restart, re-read
  every tick — the `#426` property). The store is a file the server reads,
  not a browser-held value.
- **G3 — metadata is single-source and lint-checkable.** Tags, descriptions,
  enum closed-sets, and defaults live in exactly one place and are checked
  by `lint.py` the way posture is — so a hand-edited bad value fails loud,
  not silent-fallback-unseen.
- **G4 — does not duplicate or contradict the posture concept.** Posture
  (`pace`/`asking`/`delegation`/`delivery`/`orchestration`) is already a
  code-declared closed-set with a file override. User settings must be a
  **superset that subsumes the pattern** (or explicitly an unrelated
  surface), not a second vocabulary for the same idea that drifts.
- **G5 — schema-described (kinds + defaults + enum sets), so a generic
  page renders it.** The amr-ui structural property he named: a registry
  iterable into controls, not per-setting hand-built UI.

### Ideas

- **I1 — settings table IN the ledger store; metadata in a code registry.**
  A `user_setting` table in `.dreamwork/ledger.sqlite3` (one row per
  non-default override, keyed `(userid, key)`, value as validated TEXT/JSON);
  the schema/metadata (kinds, defaults, closed-sets, tags, descriptions)
  declared in a **code registry** the DB only stores overrides against — the
  amr-ui shape, ported to SQLite. Reads via a `read_settings(target)` in
  `collect()`; writes via a new `/settings` route in
  `WRITE_ROUTE_HANDLERS`.
- **I2 — a SEPARATE settings store; metadata in a code registry.** A new
  `.dreamwork/settings.sqlite3` (or `.dreamwork/settings.json`), same
  registry-in-code model, same seam — the store is just a different file.
  Mirrors how `user-events.sqlite3` sits beside `ledger.sqlite3`.
- **I3 — metadata IN the DB per setting.** A table row carries its own
  kind/default/closed-set/description, the way `priority_band`/`task_state_kind`
  are lookup tables in the ledger store. The DB is self-describing.
- **I4 — settings as posture axes / a posture superset.** Fold every setting
  into the `.dreamwork/posture` file shape (one line per setting) and widen
  `POSTURE_AXES`; reuse `POST /posture` and the shared 10s arm.
- **I5 — localStorage (the amr-ui store layer, unchanged).** The registry
  maps; the storage is the browser, full stop.

### Matrix

| Idea | All | G1 | G2 | G3 | G4 | G5 |
|------|:---:|:--:|:--:|:--:|:--:|:--:|
| I1 · table in ledger store, registry-in-code | **✔** | ✔ | ✔ | ✔ | ✔ | ✔ |
| I2 · separate store, registry-in-code | **✔** | ✔ | ✔ | ✔ | ✔ | ✔ |
| I3 · metadata in the DB | ✘ | ✔ | ✔ | ✘ | ✔ | ✔ |
| I4 · fold into posture | ✘ | ✔ | ✔ | ✔ | ✘ | ✘ |
| I5 · localStorage | ✘ | ✘ | ✘ | ✘ | ✔ | ✔ |

### Decisive errors (the ✘s)

- **I3 refuted on G3.** Metadata-in-the-DB makes the schema
  self-describing but **fragile and un-lintable in this repo's style**: a
  closed-set declared in a DB row cannot be checked by `lint.py` against a
  reader the way posture's stop-tuples are (the closed-set discipline that
  `check_posture` enforces, `orchestrator-posture.md`), because lint reads
  *files*, not SQLite rows. amr-ui itself does NOT do this — its registry is
  code (`settings.ts`), and the DB/localStorage holds only values. A DB row
  declaring its own enum set is a second truth that a code reader cannot
  see, and a bad closed-set in a row is silent. Decisive: metadata must be
  code-declared to be lint-checkable.
- **I4 refuted on G4 and G5.** Posture is a **closed set of operational
  axes** the loop re-reads every tick to steer scheduler/wake behaviour;
  it is not a bag for arbitrary frontend preferences (dither mode,
  composer-toggle default, autogrow persistence). Folding "dither: ign"
  into `POSTURE_AXES` overloads posture's clean operational meaning the way
  `#443` measured run-mode overloading pace+asking+delegation — a
  vocabulary asked to carry unrelated decisions (G4). And posture's shape
  (one line, closed set, no per-key kind/description/tag) cannot describe
  the heterogeneous settings surface he named (G5): a number with min/max,
  an enum with display labels, a boolean with a description, are not
  posture lines. Posture is the *precedent pattern*, not the *home*.
- **I5 refuted on G1, G2, G3.** localStorage is per-browser (G1) and does
  not survive a server restart or reach the running loop (G2) — the exact
  properties `#228`/`#426` establish and amr-ui's `BroadcastChannel` only
  half-solves (intra-browser). And a browser-held value has no lint path
  (G3). This is the decisive difference from amr-ui: **its registry maps;
  its storage layer does not.**

### Two survivors — I1 and I2 tie on G1–G5

Both pass every goal: server-side (G1/G2), registry-in-code (G3/G5), and
distinct from posture (G4). The tie is real and is **not broken by
scoring** (per `igc-method.md`): the differentiator is a goal both hold
but that breaks the tie on a property the matrix does not yet name. That
property is **co-tenancy with the store that already owns this machine's
task state** — and it is escalated as Q1 with a rec, not silently flipped.

## Open calls for him — each with a rec, never picked for him

`Sub-decisions:` `Q1`, `Q2`, `Q3`, `Q4`

- **Q1 — table in the ledger store (I1) vs a separate settings store (I2).**
  **Rec: I1 — a `user_setting` table in the ledger store.** The ledger
  store is already this machine's machine-local, gitignored, WAL+FULL
  sqlite store with a migration ladder and pragma discipline; a settings
  table is one more `CREATE TABLE IF NOT EXISTS` in `_SCHEMA_SQL` and one
  migration step, reusing `open_store`/`LedgerStore` verbatim. A separate
  `.dreamwork/settings.sqlite3` (I2) is not wrong — `user-events.sqlite3`
  is the precedent for a co-resident store — but it opens a second
  connection, a second WAL pair, and a second schema-version ladder for a
  table that has no reason to live apart (settings are not append-only
  journal events with their own integrity chain; they are mutable
  key/value overrides). Co-tenancy keeps one store, one migration ladder,
  one pragma set. **The fork:** if he wants settings to travel
  independently of the task ledger (e.g. a future export/import profile
  that swaps settings without touching tasks), I2's physical separation
  earns its second file; otherwise I1 is the lighter shape.

- **Q2 — the value shape: one TEXT column + JSON validation (his "jsonb")
  vs typed columns.** **Rec: one `value` TEXT column with JSON validation
  in code, matching his sketch.** A `(userid, key, value)` row where
  `value` is a JSON-encoded scalar (bool/int/str/array) validated by the
  registry's per-kind `validate()` on write — exactly amr-ui's
  `Partial<SettingsValues>` ported to SQLite. Typed columns (a bool col, an
  int col, a text col) would force the registry to know the storage shape
  and complicate enums; one validated TEXT column keeps the row shape
  uniform and lets the registry own all type semantics. `userid` is a
  forward-looking constant in v1 (`'local'`); making it a real
  discriminator waits for `#275`/`#276` multi-user.

- **Q3 — the registry's home: a new `settings.py` vs reusing `lint.py`.**
  **Rec: a new `settings.py` module declaring the registry
  (`SETTINGS`-equivalent), imported by both `lint.py` (for the lint check)
  and `watch.py` (for read/write + `collect()`).** This is the
  single-source rule: the registry lives in one module, lint and watch
  both import it (the way watch imports `POSTURE_STOPS_*` from lint via
  `_posture_vocab()`, `watch.py` `__getattr__`). Putting the registry in
  `lint.py` directly couples frontend-preference metadata to the linter's
  concerns; a dedicated module keeps the boundary clean and is testable
  in isolation.

- **Q4 — the relationship to posture: superset, sibling, or consumer?**
  **Rec: user settings are a SIBLING surface that SUBSUMES THE PATTERN, not
  a superset that absorbs posture.** Posture stays as-is (its own file,
  its own closed set, its own `/posture` route, its own events-line
  ceremony) because it is operational state the loop's scheduler reads
  every tick — moving it under a generic settings table would break its
  tick-read contract and its lint shape. But the settings registry is the
  **generalisation of posture's pattern** (code-declared closed-set +
  file/store override + lint check), so future *non-operational*
  preferences (dither, composer-toggle default, autogrow) land in the
  registry, and posture remains the special case for the axes that steer
  the loop. Stated plainly: **posture axes are NOT user settings; they are
  posture.** A setting and a posture axis share a pattern, not a table.

## The read/write seam (settled by G1–G3, not forked)

**Read.** A `read_settings(target) -> dict` in `collect()` (alongside
`posture`/`run_mode`/`tint`), reading the `user_setting` rows and
overlaying them on the registry defaults — the amr-ui
`getSetting`-equivalent, returning `{key: effective_value}` for every
registry key. It rides the existing `/mtime` poll: `watched_mtime` walks
all of `.dreamwork/`, so a settings write (which lands in the sqlite
store under `.dreamwork/`) invalidates the cache and reaches open pages
on the next tick with **no new channel** (`watch.py:6077`). No separate
cache/mtime mechanism — the `#560` finding applies: the store files live
under `.dreamwork/`, which `watched_mtime` walks, so there is no second
cache.

**Write.** A new `/settings` entry in `WRITE_ROUTE_HANDLERS`
(`watch.py:6077`) — the single dispatch table, so E2's "every write route
commits a receipt" coverage test picks it up for free. The journal
commit/receipt (E2Shadow) runs before dispatch as it does for every write
route (`watch.py:6077`); idempotency per `#274` (identical final →
200/no-event, the ceremony posture already uses). Validation: the
handler rejects an unknown key or an out-of-set value
(`domain_invalid`), the same closed-set discipline posture uses. One
`settings via watch` events line on a real change, or none on identical
final — the run-mode/posture ceremony, unchanged.

## The frontend surface (reconciling #295 and #228)

#295's answer (`questions.md:2092`) asked for *"a settings page where we
can have a button group for these 3 options under a gfx settings section"*
— and it explicitly routed that to **#228**, the standing
unify-dashboard-settings task (`questions.md:2107`: *"the gfx settings
section belongs to #228, not to a second settings surface built beside
it"*). #228's ruling (`tasks.md.deprecated:2404`): settings **persist and
stay identical across tabs and separate browsers**, server-side, never
localStorage. So the frontend surface is:

- **One settings page/panel** (the #228 unification), driven by the
  registry — the amr-ui `SettingsPage` pattern: iterate
  `visibleSettingsByCategory()`, render one control per key grouped by
  `category`, with a per-subtype reveal for hidden rows.
- **#295's gfx section is the first `category`** — the three dither modes
  (`ign`/`white-noise`/`bayer`) as a button-group (enum with
  `control: "radio"`), the gfx settings section he named.
- **No per-surface storage.** #573's ask-me composer toggle, the #570
  autoexpand-persistence setting, and #295's dither all read the one
  registry; none invents its own `.dreamwork/` file. This is the
  anti-fragmentation property #228 exists to enforce.

The page's own placement (a `/settings` route, a popover, a sheet) is an
implementation detail for the build split, not this design — amr-ui uses a
routed `/settings` page with a settings toggle button in the header
(`App.tsx:251`); this repo's dashboard topology is different and the build
lane will place it. Not forked here.

## First consumers — each named with what it needs

- **#573 (ask-me composer toggle):** a `composer.askMeDefault` boolean
  (default off), category `Composer`. The composer reads it on open; the
  toggle is one registry entry, not a bespoke file.
- **#570 future autoexpand-persistence:** the #570 handoff (`handoffs.md`)
  notes *"the manual size is not persisted — #571 may add a setting."* A
  `composer.rememberManualResize` boolean (default off — his words: *"then
  it returns to normal behavior"*), category `Composer`.
- **#295 dither toggle:** a `gfx.dither` enum
  (`ign`/`white-noise`/`bayer`, default `ign`), category `Graphics`, with
  a button-group control — exactly the *"button group for these 3 options
  under a gfx settings section"* he asked for.

These are the seed registry entries; the registry grows as settings land,
each one lint-checked the way posture is.

## What this design does NOT authorise

A design gets read as a licence. It is not one. This doc authorises **no
code.** Matched to house style (`orchestrator-posture.md`,
`delivery-modes.md`):

- **no `watch.py` change** — not `collect()`, not a `/settings` route, not
  `WRITE_ROUTE_HANDLERS`, not a `read_settings`/`write_settings`.
- **no `ledger_store.py` change** — not a `user_setting` table, not a
  migration step, not a `LedgerStore` method. Those land in #571's
  implementation increment with their own red-first checks.
- **no `lint.py` change** — not a settings-registry lint, not an import.
- **no `file-formats.md` change** — the settings-store row and the
  registry shape land in the implementation commit, not here.
- **no `settings.py`** — the registry module is named (Q3), not created.
- **no consumer** — #573/#570/#295 read nothing until a build lands; this
  design does not wire them.
- **no migration, no deployment, no change to a running loop or live
  target.**

## Verification — how each load-bearing claim would be checked

House rule: a new check is not verification until it has been red, and the
proof must reach the real production line. This section names, for each
claim the implementation increment would rest on, how it is checked and
which line could be red.

- **A setting converges across tabs/browsers.** Check: open two browser
  windows; change a setting in one; assert the other reflects it within a
  tick via `/data.json`. **Red:** make `read_settings` cache-bust on a
  second in-memory cache instead of the store, and watch the second window
  stall. (Line: the `read_settings` call in `collect()`.) **Structural-red
  guard:** the test must read the real `collect()` output, not a fixture
  that hand-builds the settings dict.
- **A bad value fails loud, not silent-fallback.** Check: POST an
  out-of-set enum value to `/settings`; assert 4xx and the store unchanged.
  **Red:** make the handler accept an out-of-set value and watch a bad
  value persist. (Line: the closed-set branch in the `/settings` handler.)
- **The store holds only non-default overrides.** Check: write a value
  equal to the registry default; assert no row is created (or the existing
  row is deleted). **Red:** make the write path always upsert, and watch a
  default-value row appear. (Line: the default-equality check in
  `write_settings`.)
- **The registry is single-source.** Check: assert `lint.py`'s settings
  check and `watch.py`'s `read_settings` import the same `SETTINGS` object.
  **Red:** duplicate the registry in `watch.py` and watch a lint-checked
  value mismatch the rendered one.

---

--- SUMMARY ---

- **What this is:** the #571 design — persistent user settings, schema +
  seam + frontend exposure. **Design only; authorises no code.**

- **The reference (amr-ui):** its **registry model maps** — a
  code-declared `SETTINGS` registry as single source (kinds, defaults,
  tags/category, descriptions, enum closed-sets, hidden subtypes), store
  holds only non-default overrides, generic page iterates it. Its
  **storage layer does not** — amr-ui is localStorage (per-browser); #228
  ruled settings server-side, converging across tabs AND browsers.

- **The IGC headline:** **two survivors tie — I1 (table in ledger store,
  registry-in-code) and I2 (separate store, registry-in-code).** Both pass
  G1–G5 (server-side, reaches running loop, lint-checkable, distinct from
  posture, schema-described). Metadata-in-DB (I3) refuted on un-lintable
  closed-sets; fold-into-posture (I4) on overload + can't describe
  heterogeneous kinds; localStorage (I5) on per-browser + no loop reach +
  no lint. The I1/I2 tie is escalated as Q1.

- **Open calls (recs):** Q1 table-in-ledger-store over separate-store ·
  Q2 one TEXT+JSON `value` column over typed cols (his "jsonb") · Q3 a new
  `settings.py` registry module imported by lint+watch · Q4 settings are a
  SIBLING surface subsuming posture's pattern, NOT a superset absorbing
  posture (posture axes are not user settings).

- **The seam (settled, not forked):** read via `read_settings` in
  `collect()` (rides the existing `/mtime` poll — `watched_mtime` walks
  `.dreamwork/`); write via a new `/settings` route in
  `WRITE_ROUTE_HANDLERS` (E2Shadow receipt + #274 idempotency + one events
  line, the posture ceremony).

- **The frontend:** one settings page driven by the registry (#228
  unification); #295's gfx section is the first `category`; #573/#570/#295
  all read the one registry, none invents its own file.

- **First consumers:** #573 `composer.askMeDefault` (bool) · #570-future
  `composer.rememberManualResize` (bool) · #295 `gfx.dither` (enum,
  button-group).

- **Factual claims checked:** amr-ui registry/store
  (`src/lib/settings.ts:62`–`90`, `:648`–`770`, `:828`; `SettingsPage.tsx`);
  ledger store SQLite+machine-local+gitignored C1+`_MIGRATIONS`
  (`ledger_store.py:31`, `:344`–`352`; `dreamwork_db/migrate.py:28`; `.gitignore` C1); co-resident
  `user-events.sqlite3` (`user_events/sqlite.py:1`); the `/mtime`/`collect()`
  seam (`watch.py:6077`, `watched_mtime` `:4207`);
  write-route table + E2Shadow (`watch.py:6077`, `WRITE_ROUTE_HANDLERS`
  `:6077`); tint/posture read-write precedent (`:4264`, `:4394`,
  `:5863`); #228 server-side-persistence ruling
  (`tasks.md.deprecated:2404`, `:2413`); #295 gfx-section→#228 routing
  (`questions.md:2092`, `:2107`); #570 un-persisted manual size
  (`handoffs.md`).
