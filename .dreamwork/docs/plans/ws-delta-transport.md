# #614 — websocket event/RPC transport with state deltas: cost + plan (design)

Lane-owns: this doc, one doc-map row, one `## Pending` line in
`.dreamwork/handoffs.md`. **PLAN ONLY — no production code; the transport is
untouched.** His words, verbatim (receipt `a71d1105-1e41-5c73-abe7-3f2c144f5301`,
2026-07-31 ~16:35):

> "Oh a general idea I want to start implementing is to transition the
> frontend webui to a websockets based event model (with RPC) so that we can
> update the webui much faster and more efficiently, and send just partial
> state updates / state deltas rather than full state each time."

The same receipt's session-log streaming view (the other lane's task) is the
workload that most justifies this: *"we don't wanna be doing polling, uh,
rather we'll just get a notification"* — said there about the server watching
session files, and it names the goal here too: push, not poll.

## TL;DR

The waste is real and measured — but it is not where "polling is slow"
suggests. The 2-second `/mtime` poll costs 36 bytes and ~3 ms; the damage is
that the change-gate behind it is **broken open**: serving `/data.json`
itself touches `ledger.sqlite3-shm`, which advances `watched_mtime`, which
makes every open window refetch the full **917 KB** document every 2 s
forever — a self-perpetuating loop in which the dashboard's own read is the
write it then observes. Measured across a 60 s window with a real commit,
the actual content change was **5.4 KB (0.6 %)**; across a quiet 10 s window
it was **21 bytes** (the `generated` timestamp).

Four goals he named — faster, more efficient, partial updates, event model —
all survive. The mechanism he named does not survive whole: **the "with
RPC" half of a websocket transport is a second write path beside the
journal**, the exact two-parallel-descriptions drift this repo has a
standing rule against, and the RFC 6455 codec is ~250–400 lines of
hand-maintained protocol on a stdlib-only server where the browser already
ships the server→client half natively as `EventSource`. The IGC's survivor
is **SSE push of derived key-level deltas + the existing journaled POST
routes as the RPC direction** — verified live in this session: a scratchpad
SSE probe on stdlib `ThreadingHTTPServer` streamed to real Chromium,
held concurrent requests, and auto-resumed with `Last-Event-ID` after a
server-side close, with zero client reconnect code.

Phase 0 is one line (stop watching the sqlite `-shm` sidecar) and removes
most of the measured waste on its own. Phase 1 puts the delta on the
existing poll (`/data.json?since=`). Phase 2 adds the push channel carrying
the *same* delta payload. Each lands and reverts independently; the poll
remains as the fallback throughout.

## Measurements (all VERIFIED live on :35110, target = the main checkout, 2026-07-31)

| fact | value | how |
|---|---|---|
| `/data.json` payload | **917,407 B** (26 top-level keys) | `curl -w %{size_download}`, 3 runs identical |
| same, gzip -9 | 328,196 B | offline `gzip -9` — the server sends identity only (`_send`, `watch.py:4412`; response headers carry no `Content-Encoding`) |
| `/data.json` service time | 160–224 ms | `curl -w %{time_total}`, 3 runs |
| `collect()` in-process | ~300 ms | timed direct call |
| `/mtime` | 36 B, ~3 ms | curl, 3 runs |
| `watched_mtime()` walk | 485 files, 2.4 ms | timed direct call |
| poll interval | 2 s | `client/router.js:4345` (`setTimeout(tick, 2000)`) |
| mtime changed per poll | **15 of 15** samples over 30 s | curl loop at 2 s |
| what held the max mtime | `ledger.sqlite3-shm`, **34 s newer** than the newest real change | stat sweep of the watched set |
| the loop closes on itself | one `/data.json` GET moved `-shm` mtime 16:40:31.277 → 31.756, and the next `/mtime` rose | stat before/after a single fetch |
| key-level delta, quiet 10 s | `generated` only — **21 B** vs 919,946 B full | two snapshots, per-key JSON compare |
| key-level delta, 60 s incl. a commit | `git`+`burndown`+`deployed`+`generated` = **5,417 B (0.6 %)** | same method |
| largest keys | `files` 458 KB · `answered_entries` 204 KB · `dreams_archive` 161 KB · `linkable_paths` 37 KB | per-key `len(json.dumps)` |
| HTTP version | **HTTP/1.0**, no keep-alive — a fresh TCP connection per request | response line; no `protocol_version` override in `watch.py` |
| SSE on this stack works | stdlib `ThreadingHTTPServer` streamed `text/event-stream` to curl **and to real Chromium** (`EventSource`), answered concurrent `/ping` while the stream was held, and after a server-side close the browser auto-reconnected sending `Last-Event-ID: 39` — resume with **zero** client reconnect code | scratchpad probe `sse_probe.py` + Playwright, this session |

Steady-state cost today, per open window, while the loop is active: **~27 MB
per minute** of loopback transfer plus **~8–15 % of a core** in `collect()`
(160–300 ms × one build per window per 2 s tick — the build is per-request,
`watch.py:4523`, uncached). `dreamhub.py` is a second consumer of the same
pair (`dreamhub.py:15,402,425`) and pays the same 917 KB per project per
change it observes. INFERRED (not measured): the client-side cost of
`JSON.parse` on 917 KB plus the full string rebuild + morph per tick is
milliseconds-scale; the *visible* symptom class (state resets) is #505's
territory, already ruled, not this plan's.

## How today's transport actually works (VERIFIED, cited)

- Server: `http.server.ThreadingHTTPServer` (`watch.py:306–315`) — one
  daemon thread per connection, unbounded (`/usr/lib/python3.14/http/server.py:154`,
  `daemon_threads = True`); `serve_forever()` at `watch.py:5424`. A
  long-lived connection holds one thread and starves nothing — the SSE probe
  confirmed concurrent service while a stream was held.
- Client: a 2 s `setTimeout` chain (`router.js:4266–4346`) fetches `/mtime`
  (`"<generation> <watched-mtime>"`, `watch.py:4535–4539`); generation
  change → `location.reload()` (deploy/restart contract, `watch.py:77–81`);
  mtime change → full `/data.json` fetch into `setData` (`router.js:1044`),
  full rebuild, morph + snapshot/restore choreography.
- `watched_mtime` (`watch.py:3657–3695`): max mtime over `DREAMWORK.md`,
  `.git/logs/HEAD` and every file under `.dreamwork/` (minus
  `WATCHED_MTIME_IGNORED` = the question-sigs store, `watch.py:3654`), plus
  a listing-fingerprint fraction so deletions are visible (#481, #86).
  `ledger.sqlite3-shm` is **not** excluded, and sqlite touches `-shm` on
  read — including the reads `collect()` itself performs
  (`status_derive.status_from_store`, `ledger_stats`) while serving
  `/data.json`. That is the self-perpetuating loop, measured above. `-wal`
  moved only on real writes in measurement (it sat 34 s stale while `-shm`
  churned), so the write signal does not depend on `-shm`.
- Writes: 11 POST routes in one dispatch table
  (`WRITE_ROUTE_HANDLERS`, `watch.py:5308–5320`), every one behind
  `_preflight` Host+Origin (`watch.py:4281–4292`), committing a journal
  receipt before dispatch with `X-Client-Action-Id` idempotency and replay
  verdicts (`watch.py:4294–4397`), audited by `dev/reconcile_submissions.py`.
  **This is already an RPC layer with durability guarantees no fresh WS-RPC
  would have on day one.**
- `collect()` builds the 26-key document fresh per request
  (`watch.py:3422–3539`) and stamps `generated` (`watch.py:3443`) — so every
  build differs byte-wise even when nothing changed. Any whole-document
  hash/dedup must exclude it.
- Standing decisions that bind here: server stdlib-only (ruled 2026-07-30,
  #505 Q2 — the ruling freed the *client* build, `watch-design.md:41–48`);
  the current design doc says "No websockets" in its poll bullet
  (`watch-design.md:193`) — his 16:35 receipt reopens that line, and
  whatever lands must update it; two parallel descriptions drift
  (`dreamhub-design.md:197`; `DREAMWORK.md` second-truth rule); trusted-LAN
  is unauthenticated and WAN unsupported (`watch.py:5414–5417`), with
  `hub-public-auth.md` / `hub-ssh-auth.md` holding the public bar.

## The trap, named before the matrix

A delta protocol is a second description of the state unless it is
**derived**. This plan's delta is a generic function of two outputs of the
one authority: `delta(prev, next)` where both `prev` and `next` are
`collect()` documents, compared per top-level key, changed keys shipped
**whole** (a key's value is replaced, never patched). No subsystem ever
states "what changed" by hand; nothing downstream can drift from `collect()`
because nothing beside `collect()` is consulted.

Proven, not asserted, twice:

1. **Born-red reconstruction test** (server): for document pairs (including
   adversarial: key added, key removed, nested mutation, `generated`-only),
   `apply(prev, delta(prev, next)) == next` exactly. Written red first
   against a stub `delta`.
2. **Runtime self-check** (client): every delta carries `check` — a hash of
   the full document with `generated` excluded. The client hashes its
   reconstructed document; a mismatch is counted, surfaced, and answered by
   one full `/data.json` refetch — drift is *visible and self-healing*,
   never a silently wrong page.

The same rule guards the write direction: the journal envelope
(receipt/idempotency/replay/audit) stays the **one** write path. A WS-RPC
lane beside it would be the two-descriptions trap applied to writes — see
I1's decisive error.

## IGC

**Context:** stdlib-only Python server (hard, ruled); `ThreadingHTTPServer`
thread-per-connection over HTTP/1.0; consumers = N dashboard windows +
`dreamhub.py`, soon a session-log streaming view; the loop writes
`.dreamwork/` frequently; deploys restart the server (GENERATION reload
contract); trusted-LAN unauthenticated, public bar designed but not landed;
the journal is the single write authority; #591 has just ruled (pending his
ratification) that G2-no-second-render-authority is per-surface.

**Goals (binary, breakpoints stated):**

- **G1 — stdlib-only server holds.** No pip install, no non-stdlib import in
  the serving process. Hard.
- **G2 — dashboard and dreamhub keep working at every phase.** `/mtime` +
  `/data.json` semantics unbroken until every consumer has moved; no
  flag-day.
- **G3 — incremental and reversible.** Each phase lands alone, reverts
  alone, and its failure degrades to today's behaviour (the poll), not to a
  broken page.
- **G4 — supports a genuinely streaming consumer.** Server-push of an
  ordered, per-topic event stream; sub-second delivery sustained during
  bursts; survives server restart with resume. (Breakpoint: no fixed poll
  floor between event and paint.)
- **G5 — survives the repo's WAN/public bar.** Rides the existing authority
  gates (`_preflight`); exposes no audience wider than `/data.json` today;
  compatible with the hub-public-auth direction rather than adding a new
  unauthenticated surface it must later chase.
- **G6 — no second description of state, read or write.** Deltas derived
  from the one builder with a reconstruction proof; the journal remains the
  only write contract.
- **G7 — removes the measured waste.** Breakpoint: while nothing changes, a
  window transfers ~nothing (keepalive bytes); on a real change it
  transfers ~the changed bytes (measured 0.6–2 % of full), and `collect()`
  runs once per change, not once per window per tick.
- **G8 — no hand-maintained protocol machinery the platform already
  ships.** The house has ruled this shape twice: vendored morphdom over
  hand-rolled diffing (#505 Q1) and "one renderer, and it is the Python one"
  (`dreamhub-design.md:197`). Reconnect, resume, and stream framing that the
  browser provides natively must not be reimplemented by hand here.

**Ideas:**

- **I1** — full WebSocket + RPC + deltas (his words, read literally).
- **I1b** — WebSocket as push-only event pipe; POST stays the write path.
- **I2** — SSE push of derived deltas + existing POST routes as RPC.
- **I3** — long-poll (`/changes?since=`, held until change) + same deltas.
- **I4** — keep the 2 s poll; add the delta payload (`?since=`); no push.
- **I5** — do nothing structural: fix the `-shm` churn + gzip.
- **I6** — NDJSON over one long streaming `fetch()` (hand-framed SSE).

| Idea | All | G1 | G2 | G3 | G4 | G5 | G6 | G7 | G8 |
|------|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| I1 full WS + RPC | ✘ | ✔ | ✔ | ✘ | ✔ | ? | ✘ | ✔ | ✘ |
| I1b WS push-only | ✘ | ✔ | ✔ | ✔ | ✔ | ? | ✔ | ✔ | ✘ |
| I2 SSE + POST | **✔** | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| I3 long-poll delta | ✘ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✘ |
| I4 poll + delta | ✘ | ✔ | ✔ | ✔ | ✘ | ✔ | ✔ | ✔ | ✔ |
| I5 churn-fix + gzip | ✘ | ✔ | ✔ | ✔ | ✘ | ✔ | ✔ | ✘ | ✔ |
| I6 NDJSON stream | ✘ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✘ |

**The decisive errors, one per ✘:**

- **I1 ✘G6** — "with RPC" over WS means the write operations exist twice:
  once as journaled POSTs (receipt, idempotency key, replay verdict,
  Origin preflight, submissions audit — `watch.py:4294–4397`,
  `reconcile_submissions.py`) and once as WS frames that must either
  reimplement all of that or silently lack it. Two write transports
  maintained in parallel is the exact drift `dreamhub-design.md:197`
  names — and if the WS-RPC lane internally re-POSTs to dodge this, it is a
  tunnel that adds latency and code while changing nothing, i.e. not an
  idea at all. **I1 ✘G3** — handshake + frame codec + RPC correlation +
  client reconnect must all exist before the first feature works; there is
  no small first phase of "WS with RPC" that reverts alone. **I1 ✘G8** — an
  RFC 6455 server (handshake SHA-1/base64, frame parse/emit, masking,
  ping/pong, close handshake, fragmentation) is ~250–400 lines (INFERRED
  estimate) of hand-maintained wire protocol, plus hand-rolled client
  reconnect/backoff/resubscribe — all of which `EventSource` ships free for
  the server→client direction actually needed. **I1 ?G5** — the Upgrade
  handshake bypasses the request shape `_preflight` gates today; its
  Origin/Host discipline and any future auth would be a parallel
  implementation to keep in step (resolvable with care, hence ? not ✘ —
  moot under the G6/G3/G8 refutations).
- **I1b ✘G8** — drops the RPC error but keeps the whole hand-rolled codec
  and reconnect story, purely to carry events that SSE carries with
  built-in reconnect and resume (verified in this session's probe).
  Vendoring a pure-Python WS library instead would need a new ruling: the
  standing constraint is "the server imports nothing outside the stdlib"
  (`watch-design.md:46`), and #505 Q2 freed the client, not the server.
- **I3 ✘G8** — a long-poll client is a hand-maintained twin of
  `EventSource`: the fetch loop, timeout-vs-change-vs-error discrimination,
  backoff, cursor plumbing and navigation-abort all live in our code
  forever, to produce the same held-connection thread cost SSE pays on the
  server. Same shape, more of it ours.
- **I4 ✘G4** — no push: a 2 s floor between event and paint, per-event, is
  exactly the polling the streaming consumer's receipt refuses; a
  session-log view bursting many events per second cannot ride it.
- **I5 ✘G4** — same, and **✘G7**: each real change still ships the full
  document (328 KB gzipped) per window, ~60–170× the measured changed
  bytes.
- **I6 ✘G8** — reimplements SSE by hand: chunk buffering, partial-frame
  splits, reconnect, resume — everything `EventSource` does natively, as
  our code.

**Survivor: I2 — one All-✔ row.** SSE push of derived key-level deltas for
the server→client event direction; the existing journaled POST routes are
the RPC direction. My confidence: **high** on the transport choice (the
load-bearing unknowns were verified live: SSE streams from this exact server
class to a real browser, holds concurrency, resumes with `Last-Event-ID`;
delta sizes measured on the live document), **high** on phase 0's diagnosis
(the self-perpetuating loop was reproduced with a single fetch),
**medium** on the LOC estimates (marked INFERRED throughout).

His mechanism word — "websockets" — is served in substance by the survivor:
an event-pushed, delta-carrying, RPC-capable webui. Where his sentence and
the matrix part ways is only the wire protocol, and the #505 precedent
("React **or something equivalent**" → morphdom) is the house pattern for
exactly this: the goal is his; the mechanism is the one that survives his
own standing rules. The ask below puts that to him in one word.

## Phased path

Every phase: lands alone, reverts alone, poll remains the fallback. No code
is authorised by this doc.

**Phase 0 — close the broken change-gate** (~3 lines + born-red test).
Add `ledger.sqlite3-shm` and `user-events.sqlite3-shm` to
`WATCHED_MTIME_IGNORED` (`watch.py:3654`). Evidence: `-shm` moves on read
(a single `/data.json` GET moved it — measured); real writes move `-wal`
and the main db file, which stay watched, so no real change goes dark.
Born-red test: serve `/data.json` twice, assert `watched_mtime` did not
advance. Optional twin (small, separable): cache the built document keyed
by `(watched_mtime, burn_step)` so N windows cost one `collect()` per
change instead of one each per tick (`BURN_STEPS` is a closed set of 5,
`watch.py:1433`, so the cache is bounded). Effect: refetch storms stop;
windows converge on real changes only. Revert: remove the entries.
**Independently worth landing even if he rules against everything else.**

**Phase 1 — the delta, on the transport we already have**
(`/data.json?since=<v>`; server ~60–90 lines, client ~30–40, INFERRED).
The server keeps the last built document and its version (the
`watched_mtime` value it was built from). A client presenting `since`
equal to the current version gets `304`-shaped "no change"; a client one
version behind gets `{v, base, changed:{key: whole-new-value}, removed:[…],
check}`; anything else (or any mismatch) gets the full document — full is
always the safe answer. `generated` is excluded from comparison and from
`check`. Per-key compare is by serialised equality of the one builder's
output — the derived shape from "The trap" above, with its born-red
reconstruction test and client `check` self-heal. The burndown key is
compared within the same `burn_step` the client asked for (cache per step,
lazy). `dreamhub.py` adopts `?since=` at its leisure — same contract, its
poll drops from 917 KB to ~KBs per change per project. Revert: clients
that never send `since` see today's endpoint unchanged.

**Phase 2 — the push channel** (`GET /events`; server ~80–120 lines,
client ~40–60, INFERRED). SSE endpoint behind the same `_preflight` gate
in the same `do_GET` table. Events carry **the phase 1 delta payload
unchanged** — one delta implementation, two carriages — with `id:` = the
version, so `Last-Event-ID` on reconnect *is* the `since` parameter
re-used (verified free in the probe). A `: keepalive` comment every ~15 s.
Change detection: one server thread runs the existing `watched_mtime` walk
every 500 ms (2.4 ms measured — 0.5 % of a core) and publishes to
per-connection queues; each SSE connection is one daemon thread writing
from its queue (the model the server already runs; the #299 disconnect
quieting in `Handler.handle`, `watch.py:4257–4270`, already covers the
writer's `BrokenPipeError`). The generation rides every event; the client
reloads on change exactly as the poll contract does today
(`router.js:4269–4270`); a server restart drops the stream and
`EventSource` reconnects into the new generation. Client: `EventSource`
when it opens, and the existing 2 s tick loop **kept as the fallback** —
SSE failure degrades to today, which is the G3 story. A browser guard
(`dev/capture` idiom) asserts a change reaches an open page without a
`/data.json` refetch storm. Revert: remove the endpoint; the fallback is
the product again. inotify (his receipt's word) is an optimisation of this
watcher thread, not a prerequisite — stdlib has no inotify, so it would be
ctypes or a later ruling; the 500 ms stat walk meets the latency
breakpoint meanwhile.

**Phase 3 — topics for the streaming consumers** (`/events?topics=…`).
The dashboard delta stream becomes topic `data`. The session-log view (the
other lane) attaches as its own topic; its cursor is opaque to the
transport (their design names line-number + byte-offset cursors; the
transport carries per-topic cursors in event payloads and accepts them
back as query params on reconnect — `Last-Event-ID` alone is
single-valued, so multi-topic resume is explicit). Their payload schema is
theirs; this plan only guarantees per-topic ordering, resume, and the same
authority gate. **Dependency note:** nothing in phases 0–2 waits on their
design; phase 3 is where the two meet.

**Phase 4 — WebSocket, if and only if a trigger appears.** Named triggers:
a consumer needing client→server *streaming* (not request/response —
e.g. interactive terminal input to a session), or a measured SSE limit
(e.g. per-origin connection exhaustion across many tabs that HTTP/2 would
solve — not reachable on this HTTP/1.0 stdlib server anyway). Absent a
trigger, phase 4 does not exist. If triggered, it carries events only —
the journal remains the write path (I1's ✘G6 does not expire).

## Interaction with #505 G2 / lane-591g2 (scope boundary)

This plan owns the transport and the delta layer; the render layer is
ruled elsewhere (#591's analysis landed 2026-07-31: G2 per-surface,
derived-surface survivor — pending his ratification). Both branches
consume this transport identically: the client ends every delta
application holding the same full document `setData` receives today
(`router.js:1044`), so the current string-builder + morph pipeline works
unchanged; a component-native surface (if ratified) subscribes to the same
events and may additionally use the delta's `changed`-keys hint to narrow
its re-render. Nothing in this plan presumes either outcome, and no
render architecture is recommended here.

## WAN/public posture

`/events` serves the same document (as deltas) to the same audience as
`/data.json`, behind the same `_preflight` Host gate — its exposure class
is *identical by construction*, so the standing classification
(loopback/trusted-LAN; WAN unsupported, `watch.py:5414–5417`) transfers
without a new decision. The `summary()` whitelist discipline
(`watch.py:3542+`) is untouched; a future *public* stream would be a
summary-shaped topic and a separate ruling, exactly as `/summary.json` was.
When hub-public-auth lands its gate on GETs, SSE inherits it for free
because it is a GET. (This is the G5 cell's reasoning; a WS Upgrade path
would have had to re-earn it.)

## What lands where (bookkeeping when implementation is authorised)

- `watch-design.md:193` "No websockets." → rewritten to name the event
  channel and its fallback (same commit as phase 2, single-source rule).
- `file-formats.md`: the delta payload contract (`v/base/changed/removed/
  check`) when phase 1 lands.
- The phase 2 guard joins the guards registry per the standing FLAG
  discipline (coordinator-owned).

## VERIFIED vs INFERRED

**VERIFIED** (measured or read in source, cited above): every number in
the measurements table; the poll/tick mechanics; the `-shm` self-loop; the
threading model; HTTP/1.0; the 11-route journaled write path; SSE + 
EventSource + Last-Event-ID resume on this exact server class in a real
browser; delta sizes on the live document; the standing rulings quoted.
**INFERRED** (estimates/judgement, not measured): all LOC figures; the WS
implementation size range; client-side parse/render cost scale; that
long-poll client machinery ends up EventSource-shaped (argued, not built);
`dreamhub.py` adoption effort ("same contract" read from its poll seam,
`dreamhub.py:377–379`, not prototyped).

## The ask

One decision. The goals in your sentence — faster, more efficient, partial
deltas, event-pushed — all land; the analysis parts ways with it only on
the wire protocol, and since you named websockets explicitly, the
divergence is put to you rather than assumed:

**`rec`: SSE + derived deltas + existing POST RPC, phased 0→3 as above** —
push and deltas with no hand-rolled wire protocol, no second write path,
reversible at each step; websocket stays available behind named triggers
(phase 4).
**Alternative — `ws`: websocket push-only** (I1b): same phases with phase 2
swapped to a hand-rolled RFC 6455 codec (~250–400 lines to write and own,
hand reconnect/resume, a new Upgrade-path authority story) or a vendored WS
module, which would need you to relax the "server imports nothing outside
the stdlib" ruling. RPC stays on POST either way — WS-RPC beside the
journal is refuted independently of transport taste (I1 ✘G6).
**If you say nothing:** nothing is built — this doc authorises no code; when
implementation is planned, `rec` is the default and phase 0 (the `-shm`
gate fix) is proposed first in any case, since it stands on its own bug.
Accepted answers: `rec` · `ws` · free text.
