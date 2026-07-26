# `dreamnode` `/v1` — the proposed node contract (pre-plan)

Companion to `dreamhub-platform.md`, which argues *why* a node API is the
seam. This document is the contract itself, at the level of detail needed
to review it: what a client may ask for, what it gets, what it may write,
and what the relay is permitted to do in between.

**Nothing here is built.** It is written now because the shape of this
contract is the load-bearing decision in that plan (D1), and a contract
argued in prose without its fields is a contract nobody can find the hole
in.

Two properties are inherited rather than invented, and both come from
things this repo has already paid for:

- **One interpreter.** The node is the only thing that parses a
  loop-written file. Every field below is produced by the *same* reader
  `watch.py` uses today, which is what keeps `lint.py`'s guarantee
  meaningful and stops a second, subtly different open-question count from
  existing.
- **Degrade, never throw.** Every field is optional, because a fresh loop
  writes almost nothing and still has to appear. A reader that throws on a
  missing field is a page that fails to load because one project is new.

## Shape in one paragraph

Three verbs. **Resources** are addressable, cacheable documents with
ETags — you ask for what your view needs. The **event stream** carries
change *notices*, never payloads, so the client refetches what it cares
about and no delta merger exists to disagree with the reader. **Intents**
are writes with a client-minted idempotency key that return a durable
**receipt**, so a retry, a duplicated delivery, or an answer composed on a
phone while the laptop was shut all land as one write with one legible
outcome.

## Identity and scoping

| Term | Is | Stability |
|---|---|---|
| node id | a public key fingerprint, generated on first run | permanent for the machine's install |
| node name | human label (`xsm`, `x-game`) | editable; never an identifier |
| project id | assigned at `add` time from the path | permanent; **never recomputed**, for the reason the hub already learned — a recomputed slug renames an existing project when a colliding one is added, and every link that named it points elsewhere |
| project slug | the human-typeable name, node-scoped | permanent; qualified by node name when two nodes collide |

A fleet URL is therefore `…/n/<node>/p/<project>/…`, and *origin* isolation
per node is recommended in the platform plan for the artifact-XSS reason.

## Resources

`GET /v1/node`

```json
{"node": "k7f3…", "name": "xsm", "version": "2026-07-26-01",
 "now": "2026-07-26T09:41:07+10:00",
 "capabilities": ["resources", "events", "intents", "bearer"],
 "projects": [{"id": "hark", "slug": "hark", "name": "hark",
               "path_shown": "~/src/hark"}]}
```

`now` is the node's own clock, offset-aware, and it is not decoration:
every age on the page is currently computed as
`Date.now() - <server timestamp>`, which is correct only while the two
clocks are one clock. The client carries one offset derived from this
field. `capabilities` is what lets a newer website degrade **visibly**
against an older node instead of offering a control that does nothing.

`path_shown` is deliberately not the absolute path: it is what the page
displays. A hosted node has no path worth showing a human, and a shared
fleet view should not leak a directory layout to a screenshot.

`GET /v1/projects/:id/summary` — the fleet row, and the only resource the
relay may ever cache (D5).

```json
{"project": "hark", "state": "dreaming", "age_s": 41, "age_from": "last_tick",
 "task": "#231 — fold the review dock", "goal": "…",
 "awaiting_human": ["approve the LAN threat model"],
 "open_questions": 3, "queue": {"in_progress": 1, "pending": 24},
 "agents": [{"name": "dreamer-rows", "owns": ["watch.py"]}],
 "last_commit": "a0de8fc …", "deployed": {"state": "behind", "behind": 4},
 "watch": "up", "note": null, "as_of": "2026-07-26T09:41:07+10:00"}
```

Hundreds of bytes, and it is the whole fleet page. Compare the measured
**320,840 bytes** that `/data.json` returns today on this repo, of which
the fleet needs none.

`age_from` and `note` are carried forward from the hub's row contract
unchanged, including the case that matters most: a `status.json` caught
mid-write keeps its state (from the file mtime) and says its contents were
unreadable, because reporting "no status" would be a lie that flickers
once a tick.

`GET /v1/projects/:id/resources/<kind>` — one document, one ETag.

| kind | Is | Notes |
|---|---|---|
| `status` | the parsed `status.json` | plus `age_from`, as above |
| `questions` | open and answered entries, parsed | the single implementation |
| `answers` | human-to-dreamer asks | |
| `ledger` | open tasks | the ledger's readable half |
| `dreams` | active dream list (metadata) | bodies on request |
| `dreams/:name` | one dream body | up to the existing per-file read cap |
| `reviews` | artifact list | never their HTML — see artifacts |
| `git` | recent commits and touched files | the existing caps stay: 5 rows, 40 files |
| `burndown` | the ledger trend | cached on HEAD, as today |
| `file?p=<rel>` | one project file | `resolve_confined`, **per project** |
| `linkables` | the set of paths a prose renderer may link | on request, not broadcast — it is 9 KB and a full inventory of the repo |

Every response carries `ETag` and honours `If-None-Match`; a `304` is the
common case and is what makes the protocol affordable over a relay.

**Confinement is per project and is a new invariant.** One process serving
N projects must make "project A asks for project B's file" impossible, not
merely unlikely. The single-target design got this for free by having only
one root; the node must have a test that attacks it.

## The event stream

`GET /v1/events?since=<seq>` — `text/event-stream`.

```
: keepalive

id: 4821
event: change
data: {"project":"hark","resource":"questions","at":"2026-07-26T09:41:07+10:00"}

id: 4822
event: change
data: {"project":"hark","resource":"summary","at":"…"}
```

- **Notices, not payloads.** The client refetches the resource its current
  view needs. A payload-carrying stream needs a merge function on the
  client, and a merge function is a second interpreter that agrees with
  the first only on the day it is written — the same reasoning that keeps
  the hub's row rendering in Python.
- **Resumable.** `Last-Event-ID` (or `?since=`) replays notices from a
  bounded ring; a client that was away too long is told to resync rather
  than silently missing a change. "Told" matters: a stream that quietly
  loses a notice is a dashboard that quietly stops being live.
- **Keepalive comments** every ~15 s, because intermediaries and phones
  drop idle connections.
- **Polling remains supported forever.** `/v1/projects/:id/summary` with
  an ETag is the fallback, and it is what a curl-driven script or an
  offline-tolerant client uses. The local page may keep polling; the
  stream exists for links where a 2-second poll per project is rude.
- **WebSockets are scoped to one thing:** the PTY channel, if #201 is ever
  authorized. Not for reads, not for writes.

Change detection inside the node is an open measurement (U6): the stdlib
has no portable file watcher, and today's mechanism is a stat walk over
`.dreamwork/` plus `DREAMWORK.md` and `.git/logs/HEAD`. A fast walk behind
a stream interface is an honest implementation; a stream that claims to be
event-driven and is not is only dishonest if the *latency* is claimed
somewhere. It is not claimed here.

## Intents and receipts

`POST /v1/projects/:id/intents`

```json
{"idem": "01J9F2…", "kind": "answer", "at": "2026-07-26T09:41:07+10:00",
 "from": "/questions",
 "payload": {"question": "the title, verbatim", "answer": "his words"}}
```

→ `202`

```json
{"receipt": "r_8f21…", "idem": "01J9F2…", "state": "applied",
 "at": "2026-07-26T09:41:07+10:00", "detail": {"file": ".dreamwork/questions.md"}}
```

`GET /v1/receipts/:id` returns the same object; `state` is one of
`queued` (accepted by the relay, node offline), `applied`, `rejected`, or
`failed`, and it never goes backwards.

| kind | Class | Lands in | Replaces |
|---|---|---|---|
| `answer` | respond | `questions.md` | POST `/answer` |
| `note` | respond | `questions.md` | POST `/comment` |
| `ask` | respond | `answers.md` | POST `/ask` |
| `command` | steer | `watch-events.log` | POST `/command` |
| `tint` | steer | `watch-tint` | POST `/tint` |
| `lifecycle` | lifecycle | the runtime adapter | — (new, gated) |
| `pty` | runtime | the runtime adapter | — (new, gated, #201) |

Five properties, each of which is a failure this repo has already had:

1. **`idem` is required, and a repeat returns the first receipt.** One
   #233 answer arrived twice and produced two writes (#274). Over a relay
   with reconnects, at-least-once delivery is the normal case rather than
   the bug, so the write path has to be idempotent by construction instead
   of by care.
2. **The body is witnessed before it is parsed.** The existing
   `submissions.log` contract holds unchanged: one JSON line as the *first*
   act of handling, before dispatch, parse or validation, so a 400/409/413
   still leaves his words on disk. It stays machine-local and gitignored,
   because it is the only verbatim copy of what he typed.
3. **A receipt is durable and is the same object the UI polls.** This is
   #263's spine; remote steering needs it for a different reason and
   should not get a second one.
4. **The node is the single writer** for every human-write file. A node and
   a `watch.py` on one project are two processes appending to one prose
   file, and `ANSWER_LOCK` is a `threading.Lock()` — in-process only.
   Whichever way this is resolved (node-only writes, or an advisory file
   lock), the check is two concurrent appends with no answer lost.
5. **Authority is checked at the node, per class**, per the platform plan's
   grade table. The relay may forward an intent it is not permitted to
   author; the node is what refuses it, and it writes the refusal to a
   local audit log the human can read without us.

Caps and statuses carried forward from `watch.py` unchanged, because they
are already right and changing them would silently change behaviour: a
20,000-byte body cap (`413`, after the witness write), `409` when a
question title does not match, `403` on a foreign or `null` Origin for a
browser write, `421` on a Host outside the allowlist.

## Artifacts

`GET /v1/projects/:id/artifacts/:name` returns the raw HTML of
`.dreamwork/review/<name>` — and **must be served from a different origin
than the API and the app.** Today it is same-origin in an iframe, which is
fine for your own repo on your own machine and is a stored-XSS delivery
path the moment a session token exists. Served with a restrictive CSP and
embedded with `<iframe sandbox>`; the artifact list (`resources/reviews`)
stays on the API origin because it is metadata.

## Auth

Three planes, three mechanisms, one enforcement point.

| Caller | Presents | Node checks |
|---|---|---|
| local browser (loopback) | nothing | bind is loopback; Host allowlist; Origin on writes |
| LAN / mesh browser | bearer cookie (`httpOnly`, origin-scoped), issued by one-time URL or QR from the CLI | token validity + scope + Host + Origin |
| relay-forwarded session | a node-issued grant, short-lived and named | grant validity + scope + intent class + rate |
| CLI / script | bearer header | token validity + scope |

- **Never a token in a query string.** It lands in logs, history and
  referrers, and the one-time link that *delivers* it is the exception
  that is single-use and short-lived.
- **#233's gates stay.** Exact Host allowlist on every request before any
  target read; Origin on browser writes before the body is read. They stop
  DNS rebinding and a foreign site driving the browser, and they are still
  not login.
- **Scopes are enumerated, not implied**: `read`, `respond`, `steer`,
  `lifecycle`, `pty`, and `configure` — with `configure` never reachable
  through the relay.
- **Revocation is local and works offline**: `dreamnode tokens revoke`,
  `dreamnode unlink`. A kill switch that requires our website to be up is
  not a kill switch.

## The relay link

The node dials out; the relay never dials in. One WSS connection carries
framed requests and responses plus streams, with a request id per
exchange.

```
node → relay :  HELLO {node, version, capabilities, sig(challenge)}
relay → node :  REQ   {rid, method, path, headers, body}
node  → relay:  RES   {rid, status, headers, body} | CHUNK{rid, …} | END{rid}
node  → relay:  PUSH  {summary | needs-human}          (node-initiated)
relay → node :  DELIVER {sealed intent envelope, receipt id}
```

- **Outbound-only** means no port forwarding, no DNS, no certificate for
  the user, and CGNAT works.
- **`DELIVER` carries sealed envelopes.** An intent composed while the node
  was offline is encrypted to the node's public key; the relay holds a
  receipt id and a TTL and cannot read the payload. This protects data *at
  rest only* — TLS terminates at the relay, so live traffic is readable by
  it and any claim otherwise would be false while we also serve the
  client JS.
- **`PUSH` is what makes the fleet and notifications work**: the node
  volunteers its summary (subject to D5's consent) and volunteers the fact
  that a human is needed. Default notification content is the project and
  the count, never the question text.
- **Reconnect is expected.** Receipts and event sequence numbers exist so a
  reconnect is a resync rather than a gap, and so at-least-once delivery
  is a normal case with a defined outcome.

## Versioning and skew

- The path carries the major version (`/v1`); fields are added, never
  repurposed.
- `capabilities` is the negotiation surface, and the website's contract is
  to **say what a node cannot do** rather than to hide it or to offer it
  and fail. A control that does nothing is the failure mode this repo has
  already had once, in the command channel nothing read.
- Two repos make skew normal rather than exceptional: the website will
  routinely talk to nodes older than itself, and the guard for that is a
  contract test run against the *oldest supported* node, in the same spirit
  as the hub's cross-contract guard — run the real one over a copy, and
  assert the aggregate agrees with it.

## What this contract does not do

- **No cross-project aggregation inside the node.** The fleet is composed
  by the client (or the relay) from summaries, so nothing here mints a
  second aggregate that can go stale.
- **No task ids, no queue writes.** Unchanged from the hub's edge: the node
  reads the ledger and never mints an id.
- **No lifecycle in v1's default posture.** The verbs exist in the table
  so the capability negotiation has something to say; they stay denied
  until `daemon-mode.md` stage 2 lands the runtime adapter and the human
  grants them per project.
- **No delta payloads, no client-side merging, no second renderer.**
