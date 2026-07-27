# #310 — `dreamhub.py` vs `dreamhub-design.md` drift audit

Read-only audit. Every finding below was checked against the cited code line,
not assumed from the doc. Scope: the four data sources the doc names
(`status.json`, `watch-port`, `/mtime`, `/data.json`), the routes, the
state homes, the page/styling claims, the stage-1 boundary, and the
verification claims. `file-formats.md` is read as the *other* document making
claims about the same `status.json` interface (per the task's category #3).

Verdict: the field/endpoint/path claims are almost entirely accurate — no
doc-named field is missing from the code, and the token parity (`--warn
#fcd34d`, `--accent #a5b4fc`, `--bg #0b0f19`) is exact against `watch.py`.
The drift is concentrated in (a) the `agents[]` subfields where the two docs
disagree, (b) one stale verification claim, and (c) one undocumented runtime
dependency. Five findings, most severe first.

---

## 1. `agents[].owns` — the hub renders it; the writer's contract omits it

The task names this shape as the most dangerous: two documents describing one
interface. It is real here.

**Doc claim (`dreamhub-design.md`).** The hub's dependency table lists `owns`
as a field it reads and renders:

- `dreamhub-design.md:88` — `` | `agents[].name`, `agents[].owns` | "N out: name (owns)" | a nameless agent renders as `?`; a non-list `owns` renders as none | ``
- `dreamhub-design.md:76-77` — "This section states what the hub **uses** … two docs, no overlap."

**What the code does.** `dreamhub.py` reads `owns` and renders it in the facts
line:

- `dreamhub.py:341` — `"owns": [str(o) for o in _as_list(a.get("owns"))],`
- `dreamhub.py:673` — `f'{esc(a["name"])}<span class="owns"> ({esc(", ".join(a["owns"]))})</span>' …`

So the hub does what the design doc says. CONFIRMED.

**Where the drift is.** `file-formats.md` is the writer's contract for
`status.json` (it is the file `CLAUDE.md` points writers at: "Files the loop
writes and a tool parses have their shape stated in `file-formats.md`"). Its
`agents` row does not list `owns` at all:

- `file-formats.md:494` — `` | `agents` | array of objects, each with at least `name` | live subagents; a reader shows the count and the names. Optional per agent: `kind` … and `awaiting_result` … | ``

`owns` is absent. A loop that writes `status.json` to this contract would never
emit `owns`, and the hub would render every agent as `name ()` — empty
parens, silently. The fixture writes it (`dev/hub/fixture/fresh/.dreamwork/status.json:6`,
`"owns": ["dreamhub.py", "dev/hub/"]`), which is why no test catches the gap:
the fixture is authored by the hub's own dreamer, not generated from
`file-formats.md`. Note `watch.py` does **not** read `owns` (every `owns` hit
in `watch.py` is English prose, not a field read), so the hub is the *only*
reader — there is no second reader to notice the omission either.

**Smallest correction.** DOC changes; the code is right. Add `owns` (optional,
array of strings) to `file-formats.md:494`'s `agents` row. The design doc and
the code already agree.

---

## 2. "Not yet wired into `just test`" is stale — the hub guards ARE wired in

**Doc claim (`dreamhub-design.md`).** Stated as present-tense fact:

- `dreamhub-design.md:203-205` — "See `dev/hub/README.md`. **Not yet wired into `just test`** — that line belongs to the justfile's owner and is #134. Until it lands, a green `just test` does not cover the hub."

**What the code/infra does.** The `guards` recipe (a dependency of `test`)
runs the hub guards, and #134 landed:

- `justfile:130` — `` HUB_GUARDS=${DREAMWORK_HUB_GUARDS-"hub contract"} ``
- `justfile:183` — `for h in $HUB_GUARDS; do … node "dev/hub/$h.mjs" "$OUT/$h" …`
- commit `09e3397 justfile: the hub's guards run in `just test` (#134)`

`dev/hub/README.md:27` already assumes the wiring ("the justfile lines that
wire these in (#134) carry no port and no plumbing"), so the README and the
design record now disagree with each other about whether #134 shipped.

The cost of leaving it: a reader trusts the design record over the justfile,
believes a green `just test` does not cover the hub, and either re-runs the
guards by hand every time or — worse — stops trusting `just test` for hub
changes on the grounds that "it doesn't cover this anyway."

**Smallest correction.** DOC changes. Replace lines 203-205 to state the
guards run in `just test` via #134, and drop the "Until it lands" sentence.
(If the verification section's three-bullet structure is kept as a record of
*what each check sees*, that's fine — but the "not wired" / "does not cover"
sentences are false now and must go.)

---

## 3. `agents[].in_flight` is read by `dreamhub.py` and served in `/hub.json`, but is in neither doc

**What the code does.** The agent reader captures a third subfield beyond
`name`/`owns`:

- `dreamhub.py:342` — `"in_flight": a.get("in_flight")}`

It is not escaped or type-checked (unlike `name`/`owns`, which are
`str(...)`-coerced and list-normalised). It is carried into the row dict and
so into `/hub.json` verbatim (`do_GET` at `dreamhub.py:833-837` dumps `rows`).

**That it is a real field, not fixture noise.** `watch.py` reads it as a
first-class agent field:

- `watch.py:1882` — `const ST_AGENT_GLANCE = ['name', 'in_flight'];`
- `watch.py:1902` — `` `</span><span class="stdoing">${mdInline(String(a.in_flight || '—'))}` ``

Both fixtures write it (`dev/hub/fixture/fresh/…/status.json:7,10`,
`dev/capture/fixture/.dreamwork/status.json:9,17`).

**Where the drift is.** Neither document mentions it:

- `dreamhub-design.md` — grep for `in_flight` returns nothing. The dependency
  table (`dreamhub-design.md:88`) lists only `agents[].name` and
  `agents[].owns`.
- `file-formats.md:494` — lists `name`, `kind`, `awaiting_result`; no
  `in_flight`.

So two readers depend on `in_flight` and neither doc records it. If it is
renamed (or a writer drops it because the contract doesn't ask for it),
`/hub.json` consumers and the watch dashboard both degrade silently, and
nothing in either design record warned a maintainer that it was load-bearing.

**Smallest correction.** DOC changes. Add `in_flight` (optional, string — a
one-line claim of what the agent is doing right now) to the `agents` row in
**both** `file-formats.md:494` (writer's contract; two readers use it) and
`dreamhub-design.md:88` (the hub reads and republishes it). Separately
consider whether `dreamhub.py:342` should `str()`-coerce it for consistency
with its siblings — but that is a code-tidiness call, not drift, and is
out of scope for "which doc is wrong."

---

## 4. `deployed.py` is an undocumented runtime dependency, in tension with "one stdlib file"

**What the code does.** The dashboard-staleness feature path-loads a sibling
module by filename:

- `dreamhub.py:452-458` — `def _load_deployed(): … path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deployed.py") … spec.loader.exec_module(mod)`
- called from `probe_deployed` (`dreamhub.py:471`) and `probe_all`
  (`dreamhub.py:507`).

That module reads the deploy snapshot (`deployed.py:45,73` →
`~/.cache/dreamwork/deployed/<basename>-watch.py`) and runs git against the
repo. So the hub depends on three things the design doc never names: the
`deployed.py` file existing beside it, the `~/.cache/dreamwork/deployed/`
directory, and the repo's git history of `watch.py`.

**Doc claim (`dreamhub-design.md`).** The "What the hub depends on" section
(`dreamhub-design.md:73-123`) enumerates exactly four data sources
(`status.json`, `watch-port`, `/mtime`, `/data.json`). A grep of
`dreamhub-design.md` for `deployed.py` / `.cache` / the snapshot path finds
nothing — only `dreamhub-design.md:70` ("`just deploy`'s snapshot pattern")
and `dreamhub-design.md:167` (the `never deployed` *state*). The staleness
*feature* is described (`dreamhub-design.md:158-172`); the *dependency* is not.

It also sits in tension with a concrete claim:

- `dreamhub-design.md:70` — "`dreamhub.py` stays one stdlib file so `just deploy`'s snapshot pattern applies to it unchanged."

Two problems with that line as written: (a) `just deploy` snapshots **only
`watch.py`** (`justfile` `deploy` recipe: `git show {{rev}}:watch.py > "$snap"`),
not `dreamhub.py`, so "applies to it" is already loose; and (b) if
`dreamhub.py` *were* copied to a snapshot dir alone, `_load_deployed()` would
fail to find `deployed.py`, the broad `except` at `dreamhub.py:507-509` would
set `mod = None`, and **every row would silently lose its `.stale` line** —
the one signal this whole feature exists to show. "Applies unchanged" is true
only in the sense that the page still loads, minus the feature.

**Smallest correction.** DOC changes. Add `deployed.py` (and the cache dir it
reads) as a fifth dependency in "What the hub depends on," and clarify
`dreamhub-design.md:70`: the snapshot pattern applies to `watch.py`; the hub
is served from the working tree and path-loads `deployed.py`, so it is not
itself snapshot-safe (and degrades gracefully — no `.stale` lines, not a
crash — if that module is absent).

---

## 5. (minor) `contract.mjs` "holds all four of these to account" overstates its scope

**Doc claim.**

- `dreamhub-design.md:122-123` — "`dev/hub/contract.mjs` is the guard that holds all four of these to account against a real `watch.py`."

"All four" refers to the four subsections above it: `status.json`,
`watch-port`, `/mtime`, `/data.json`.

**What the guard actually does** (`dev/hub/contract.mjs`):

- asserts `/mtime` is the two-part `"<gen> <mtime>"` key (`contract.mjs:102-103`);
- asserts `/data.json` carries `open_questions` as a number (`contract.mjs:104-108`);
- asserts the hub agrees with watch on the count and **follows** a change
  (`contract.mjs:141-172`).

It writes `watch-port` itself (`contract.mjs:67`) and rides on the fixture's
`status.json`, but it asserts nothing about `status.json` field parsing or
`watch-port` semantics. So it holds the **live protocol** (two of the four) to
account, not all four. `dev/hub/README.md:48-58` describes it the same narrower
way: "Stage 1 has exactly one cross-file dependency … a protocol … polls
`/mtime` and re-reads `/data.json`." The design record is the one that rounds
that up to "all four."

The disk half (`status.json`, `watch-port`) is covered by `test_dreamhub.py`'s
`TestProbeDisk`, not by `contract.mjs` — so the *coverage* exists, it is just
attributed to the wrong guard by this sentence.

**Smallest correction.** DOC changes. Either narrow "all four of these" to
"the live half of these" / "the `/mtime` and `/data.json` contract," or name
both guards: `contract.mjs` for the live protocol, `test_dreamhub.py` for the
disk fields.

---

## Verified accurate (checked, not findings)

For confidence that these were inspected and held up, not skipped:

- **`status.json` fields the doc names** (`last_tick`, `task`, `goal`,
  `awaiting_human`, `agents[].name`, `agents[].owns`, `queue.pending`,
  `last_commit`) — all read at the cited behaviour, including the
  `last_tick`→mtime fallback with `age_from:"file"` (`dreamhub.py:309-312`),
  the `awaiting_human` list-coercion (`dreamhub.py:333-334`), and the
  `goal`/`last_commit` " `/hub.json` only" routing (read at `:325,:328`,
  absent from `render_row`).
- **`.dreamwork/watch-port`** — read-only, one-line integer
  (`dreamhub.py:262-270`); hub never writes it (the write-nothing test
  `test_the_hub_writes_nothing_outside_its_own_home`, `test_dreamhub.py:823`).
- **`/mtime` whole-string cache key** (`dreamhub.py:402,421`); **`/data.json`
  uses only `open_questions`** (`dreamhub.py:437`).
- **State homes** — `projects.json` (`dreamhub.py:55`), hub `port`
  (`dreamhub.py:795`), aggregate in-memory per request (`dreamhub.py:832`),
  slug assigned once at add time (`dreamhub.py:189`).
- **Token parity** — `--warn #fcd34d` (== `watch.py:333`),
  `--accent #a5b4fc` (== `watch.py:324`), `--bg #0b0f19` (== `watch.py:321`).
  `--warn`'s single user is `.stale` (`dreamhub.py:595`); the accent is spent
  on exactly the three things the doc names (`dreaming` `:587`, `.facts .q`
  `:580`, `.waiting` `:575`).
- **Stage-1 boundary** — `127.0.0.1`-only bind (`dreamhub.py:856`), no
  lifecycle (down row shows the command, missing row shows none:
  `dreamhub.py:688-700`), origin-per-project not proxy (links out:
  `dreamhub.py:738-740`).
- **One renderer** — `/` and `/rows` share `render_rows` (`dreamhub.py:838-841`);
  the page polls `/rows`, not `/hub.json` (`dreamhub.py` SCRIPT `:627`).

## Out of scope but noted

- `file-formats.md:494` also lists `agents[].kind` and `agents[].awaiting_result`,
  which **no reader in this repo consumes** (`awaiting_result` appears only in
  `file-formats.md` itself; `kind` is not read by `dreamhub.py` or `watch.py`'s
  agent glance). That is a `file-formats.md`-internal over-spec, not a
  `dreamhub` drift, so it is flagged here rather than as a finding — but it is
  the same shape as finding 3 in the other direction, and worth a line in
  `file-formats.md` when findings 1 and 3 are addressed.
