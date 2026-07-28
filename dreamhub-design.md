# dreamhub.py — one page over several dreaming projects (design record)

Stage 1 of the daemon-mode staging (`.dreamwork/docs/plans/daemon-mode.md`),
planned in detail in `.dreamwork/docs/plans/dreamhub-stage1.md` and built to
that plan. Human go 2026-07-25 10:48, and narrow: **stage 1 only.**

## What it is

A read-only aggregate over several dreamwork targets on this machine. A
registry the human edits from the CLI, and one page that says, per project:
whether the loop is dreaming or has gone quiet, what it is working on,
**whether it is waiting on him**, how many questions are open, which dreamers
are out and what they own — and a link through to that project's own watch
dashboard.

The value nothing else provides: **one glance tells him which of his dreamers
has stopped moving.** Today that is N bookmarks and remembering which ports
exist.

It computes almost nothing of its own. Almost every fact on the page is read
live from that project's `.dreamwork/` or from its running watch instance.

## What it is not, and how each edge is checkable

| Not | Checked by |
|---|---|
| No lifecycle — no start/stop/pause/spawn/kill | a down row shows the *command*; `hub.mjs` asserts a `missing` row offers no command at all |
| No writes to any target | `test_the_hub_writes_nothing_outside_its_own_home` compares every file under the targets before and after a request |
| No second questions.md parser | no parsing code exists; a down watch reports `None`, and the page says "questions unknown" |
| No second task list — never mints an id, never holds a queue | nothing in `dreamhub.py` writes a task |
| No remote, no non-localhost bind, no auth | binds `127.0.0.1` by construction |

Those edges are the approval. A stage with no edge grows one.

## The one deviation from `daemon-mode.md`

`daemon-mode.md` sketched `/{project}/…` reverse-proxying to each target's
watch port. Stage 1 ships **origin-per-project** instead: the hub lists and
links out, and each project keeps its own port and its own URLs.

Measured, not guessed. `watch.py`'s page is root-absolute in three places, and
the third is the one no external shim can reach: `routeOf()` and
`isInternal()` compare `location.pathname` against the literals `'/'`,
`'/questions'`, `'/file'`, `'/review'`. A proxy can patch what a page *calls*
(`fetch`, `pushState`); it cannot patch what a page *reads*. So a prefixed
deep link would have loaded, rendered, and shown the wrong view — silently.

Origin-per-project is not a local-only shortcut either: `ssh -L` gives a local
port per remote project, which is the same shape, so the prefix never has to
be solved to reach the swarm stage. The prefix is filed against #124's
server-core seam, where those three sites are being touched anyway.

## The reuse rule

**Protocol, styleguide, and guard contract — never code. No `import watch`.**

Per project the hub polls `GET /mtime` and re-reads `GET /data.json` only when
it changes. That is the same contract watch's own client uses, so the hub
costs a running watch almost nothing, and `/mtime` doubles as the liveness
check.

The consequence worth stating plainly: **the hub never parses
`questions.md`.** The open-question count keeps exactly one implementation,
and when that implementation is not running the hub says *unknown* rather than
computing a second, subtly different answer.

The trade, bounded: *duplicate trivia (a `read_text`, an age formatter), never
duplicate an interpreter (a parser, a counter, a classifier).*

`dreamhub.py` stays one stdlib file so `just deploy`'s snapshot pattern
applies to it unchanged — with one caveat that line used to hide (#310):
`just deploy` snapshots **`watch.py` only**, and the hub path-loads
`deployed.py` from its own directory (`_load_deployed`). A hub copied
somewhere alone still serves; it silently loses every `.stale` line, which
is the one signal that feature exists to show. It degrades, it does not
crash — but "applies unchanged" means the page, not the feature.

## What the hub depends on

`file-formats.md` states what a loop **promises** to write. This section
states what the hub **uses** — two docs, no overlap. Every field is optional
and every one degrades; a fresh loop writes almost nothing and still has to
appear as a row.

### `.dreamwork/status.json` (read from disk)

| Field | Used for | If absent or the wrong type |
|---|---|---|
| `last_tick` | the age, and therefore the state | falls back to the file's mtime, and the row says so (`age_from: "file"`) |
| `task` | the row's second line | omitted |
| `goal` | `/hub.json` only | omitted |
| `awaiting_human` | **the accented line above the task** | omitted |
| `agents[].name`, `agents[].owns` | "N out: name (owns)" | a nameless agent renders as `?`; a non-list `owns` renders as none |
| `agents[].in_flight` | `/hub.json` only — republished verbatim | omitted. **Also read by `watch.py`**, which promotes it into the agent glance line (`ST_AGENT_GLANCE`), so it has two readers and is the one agent subfield a writer should treat as load-bearing (#310) |
| `queue.pending` | "N pending" | omitted |
| `last_commit` | `/hub.json` only | omitted |

`awaiting_human` is the one field that must never be buried. A row reading
`quiet` over a loop that has actually stopped for him is the most expensive
wrong impression this page can give: he walks away from a dreamer waiting on
one sentence.

**The file is read while it is being written.** It is rewritten every tick, so
the hub *will* catch one mid-write. A torn file keeps its state (from the
mtime — a target caught mid-write is dreaming harder than any other row) and
says its contents are unreadable. Reporting it as "no status" would be a lie
that flickers once a tick.

### `.dreamwork/watch-port` (read from disk)

One line, an integer, persistent — it is the address his bookmark points at.
**The hub never writes it.** Absent means the project has never been watched.

### `GET /mtime` (from a running watch instance)

`"<generation> <mtime>"`. The whole string is the cache key, both halves: a
changed mtime means the data changed, a changed generation means the server
was rebuilt and any cached document is from a different build.

### `GET /data.json` (from a running watch instance)

Only `open_questions` (an integer) is used. Everything else is ignored — and
deliberately not stored, because `/data.json` currently carries the full text
of `DREAMWORK.md`, `questions.md` and `lessons.md`. That is fine on a
change-triggered fetch over localhost and is exactly what stops being fine
over a link, which is why a light `/summary.json` is noted for stage 3.

`dev/hub/contract.mjs` holds the **live half** of these to account against a
real `watch.py` — the `/mtime` key shape, `/data.json`'s `open_questions`, and
that the hub follows a change. The disk half (`status.json` fields,
`watch-port`) is covered by `test_dreamhub.py`'s `TestProbeDisk`, not by the
browser guard. Naming one guard for all four read as coverage this file does
not have (#310).

## State — one home per fact

| Fact | Home |
|---|---|
| Which projects exist | `~/.config/dreamwork/hub/projects.json` |
| The hub's port | `~/.config/dreamwork/hub/port` |
| A project's status, questions, port, git | that project's own `.dreamwork/` — **read only, never copied** |
| The aggregate | in memory, per request |
| Code, tests, guards, fixture, this doc | this repo |

The registry is a fact about *this machine*: committing it would be wrong on
the next machine and would leak local paths. A cached copy of a project's
state would be a second source of truth that goes stale exactly when it
matters. Nothing in stage 1 is added to `.gitignore`, because all the hub's
mutable state is outside the repo by construction.

**The slug is assigned once, at `add` time, and never recomputed.** A slug
recomputed on read is a function of the whole registry, so removing one
project silently renames another — and every link, bookmark and log line that
named it then points somewhere else.

## The page

Tokens are `watch-design.md`'s, value for value: the human moves between this
page and a project's dashboard constantly, and a second palette would read as
a second product. Mono stack, two sizes, dim uppercase labels, hairlines not
boxes, `72ch` column.

The accent is scarce and spent only on what is live or actionable: a
`dreaming` state, a nonzero open-question count, `waiting on you`, and the
row's one link — the project name, an accent-coloured anchor only when its
watch is `up`. Everything else, including `stalled` and `missing`, is stated
plainly — the page is read at a glance, and a wall of red says nothing.

**One second colour, and it means BROKEN rather than live** (`--warn`,
`#fcd34d`, watch.py's value). It has exactly one user: `.stale`, the line
saying a project's dashboard is serving code older than its HEAD (#147).
That is worth amber because it is the failure where the page he is reading
looks correct and is not — a past presented as the present. It is
deliberately not the accent: the accent marks what is live and actionable,
and spending it here would cost the page its loudest signal.

**The staleness line is silent when there is nothing wrong.** `current`
and `never deployed` render nothing at all; only `behind` and `untracked`
appear. A line on every healthy row is the noise that hides the one
unhealthy row — the same reason `watch-tint` warns on a bad value and says
nothing when unset. The summary is the line and the individual missing
commits are in its `title`, so hovering gives the whole list without the
row growing to hold it (detail is ranked, never withheld).

**Label the columns, not the gaps.** Every row states its facts under a header
pair (`PROJECT` / `LAST TICK`).

**One renderer, and it is the Python one.** `/` serves the page, `/rows`
serves the same fragment, and the client swaps the fragment rather than
building rows of its own. `/hub.json` is the machine-readable aggregate and
is not what the page polls — polling it would mean a JS row renderer beside
the Python one, and two renderers only agree on the day they are written.
(This is a deviation from the plan's I7 wording, in service of the plan's own
reuse rule.)

Ages tick client-side every second off `data-since`. That is invisible while
polling works; its job appears when the hub cannot be reached, where the last
known tick is still a fact and its age genuinely keeps growing. A page that
froze instead would say a project ticked more recently than it did. When the
poll fails the page says `not reaching the hub` rather than pretending.

## Verification

Two halves, because neither can see what the other sees.

- `pytest test_dreamhub.py` — the registry, the probes, the render's
  *generated source*, and the server's routes. It cannot see what renders.
- `node dev/hub/hub.mjs <OUT> [<PORT>]` — a real browser over a real server:
  rows present *and visible*, states distinct, liveness, no overflow, and
  screenshots for a human to look at.
- `node dev/hub/contract.mjs <OUT> [<PORT>]` — a real `watch.py` over a copied
  fixture, asserting the hub agrees with it and follows a change.

See `dev/hub/README.md`. **Wired into `just test`** since #134 (`09e3397`):
`test` depends on `guards`, which runs `$HUB_GUARDS` (`hub` and `contract`),
so a green `just test` does cover the hub. This paragraph claimed the
opposite for as long as it was false, and `dev/hub/README.md` already
assumed the wiring — two records of one fact, disagreeing (#310).

Every check in all three was shown failing on the bug it claims to catch
before it was trusted. Two checks passed on their own bug the first time and
were rewritten; both were only visible by injection.
