# #428 — guard readiness census (the concurrency class)

**Scope.** Every `dev/capture/*.mjs` guard characterised by its two readiness
layers, following the #507 folded line (`.dreamwork/handoffs.md`). The class
has two layers that race a fixed `sleep` under load:

1. **Server readiness** — an own-server guard spawns `watch.py` then
   `sleep(2500)` + a `fetch /data.json`; under load python outlasts the sleep
   → the fetch throws `ECONNREFUSED` (or grades a stranger on the port) → the
   guard "threw before finishing" over a correct server. The fix idiom is
   `serveVerified` (`dev/capture/serve.mjs`, #461): it spawns, **polls**
   `/data.json` until the responder answers, and **proves the target is ours**
   before returning.
2. **Render readiness** — `goto … networkidle` returns when `data.json` is
   fetched, but the client JS that BUILDS the DOM the assertion reads has not
   run yet; a fixed `sleep` after it grades a half-rendered page. The fix
   idiom is the shared `waitFor(page, sel, timeout)` (`dev/capture/dom.mjs`,
   #507): wait for the specific selector instead.

**How this table was derived.** Server layer is read from each guard's spawn
block (a real `/data.json` poll loop = safe; a bare `sleep` = defective; the
harness-owned shared server = harness's problem, safe here). Render layer is
the first thing that touches the DOM after a `goto`/`reload`: a selector wait
or a Playwright auto-wait action (`click`/`fill`/`locator`) is gated (safe); a
direct `evaluate` preceded only by a `sleep` is the defective shape.

## Server layer

| guard | server readiness | note |
|---|---|---|
| bdhover | serveVerified | #507 |
| burndown | serveVerified | #507 (two servers) |
| filehead | serveVerified | #461 |
| filehl | serveVerified | #461 |
| fileimg | serveVerified | #461 |
| fileview | serveVerified | #461 |
| gitrow | serveVerified | #461 |
| identity | serveVerified | #461 |
| qsignal | serveVerified | — |
| rejectwrite | serveVerified | #461 |
| reviewdraft | serveVerified | #461 |
| serving | serveVerified | #461 |
| staleremedy | serveVerified | #461 |
| summaryjson | serveVerified | #461 |
| health | serveAllVerified | #461 (multi-target) |
| above_fold | own-poll (safe) | polls `/data.json` in a 10s loop, identity-checked |
| provenance | own-poll (safe) | polls `/data.json` 40×, identity-checked |
| revieworder | own-poll (safe) | `--port 0`, reads bound port from stdout |
| **bdinput** | **own-sleep DEFECTIVE** | `spawn`+`sleep(2500)`+fetch identity |
| **posture** | **own-sleep DEFECTIVE** | `spawn`+`sleep(2200)`, NO identity check |
| **projtitle** | **own-sleep DEFECTIVE** | `spawn`+`sleep(2500)`+fetch identity |
| **dashboard** | **own-sleep DEFECTIVE** | `spawn`+`sleep(2500)`+fetch identity |
| **motion** | **own-sleep DEFECTIVE** | `spawn`+`sleep(2500)`+fetch identity |
| **morph** | **own-sleep DEFECTIVE** | `spawn`+`sleep(2500)`+fetch identity |
| **morphhold** | **own-sleep DEFECTIVE** | `spawn`+`sleep(2500)`+fetch identity |
| **devoverlay** | **own-sleep DEFECTIVE** | `spawn`+`sleep(2500)`+fetch identity (`--dev`); 2nd server `rsrv` same |
| *(all others)* | shared (harness) | take `PORT` from argv; the justfile owns server readiness (pre-flight + identity probe) |

**Server-defective set: 8 guards** — `bdinput posture projtitle dashboard
motion morph morphhold devoverlay`. All pick an ephemeral port via `freePort()`
and gate readiness on a fixed `sleep`. Under load python's startup outlasts
the sleep and the `fetch` either throws (no try/catch on 6 of 8 → "threw
before finishing") or, on `posture`, grades a stranger with no identity check
at all. This is the acute layer of the #428 concurrency failure.

## Render layer

Categories: **waitFor** (dom.mjs shared gate, the #507 idiom); **auto-wait**
(first DOM touch is `click`/`fill`/`locator`/`waitForSelector`/
`waitForFunction`, which Playwright auto-waits — safe); **sleep→eval** (a
`sleep` then a direct `evaluate` read with no selector gate — the defective
shape); **tolerant** (a `sleep→eval` whose first check is an existence/absence
gate that FAILs with a message rather than crashing — sleep-gated but safer).

| guard | render readiness | server | first read |
|---|---|---|---|
| bdhover | waitFor | serveVerified | `.bdcol[data-open]` |
| burndown | waitFor | serveVerified | `.bdbar[data-bk], .bdnone` |
| mdquote | waitForSelector | shared | quote selector |
| mdtable | waitForSelector | shared | table selector |
| submitlog | waitForSelector | shared | — |
| above_fold | waitForSelector | own-poll | review frame |
| noteprop | waitForFunction | shared | dock present |
| docktarget | waitForFunction | shared | dock present |
| burndownmock | waitForFunction | shared | — |
| provenance | waitForFunction | own-poll | — |
| cmdcap | click (auto-wait) | shared | `#cmdplus` |
| confirmation | click (auto-wait) | shared | `#cmdplus` |
| dismiss | click (auto-wait) | shared | card |
| draft | click (auto-wait) | shared | composer |
| indicator | click (auto-wait) | shared | — |
| menucap | click (auto-wait) | shared | — |
| popbg | click (auto-wait) | shared | — |
| rejectwrite | fill (auto-wait) | serveVerified | — |
| fileview | click (auto-wait) | serveVerified | — |
| gitrow | click (auto-wait) | serveVerified | — |
| typing | click (auto-wait) | shared | — |
| answers | locator (auto-wait) | shared | `#askbox` |
| **subslog** | **sleep→eval DEFECTIVE** | shared | `__dwSubmissions()` (#428 named) |
| qacard | sleep→eval | shared | card |
| reflow | sleep→eval | shared | surface |
| headertravel | sleep→eval | shared | bar |
| headcrumb | sleep→eval | shared | crumb |
| history | sleep→eval | shared | panel |
| note82 | sleep→eval | shared | card |
| oneinput | sleep→eval | shared | card |
| pip83 | sleep→eval | shared | pip |
| plugcmd | sleep→eval | shared | palette |
| prominence | sleep→eval | shared | card |
| qfade | sleep→eval | shared | fade |
| qfocus | sleep→eval | shared | focus |
| qlinkpip | sleep→eval | shared | link |
| qorder | sleep→eval | shared | order |
| qroll | sleep→eval | shared | roll |
| qsec | sleep→eval | shared | ghost |
| qsignal | sleep→eval | serveVerified | signal |
| regroup | sleep→eval | shared | cards |
| research | sleep→eval | shared | surface |
| restcollapse | sleep→eval | shared | fold |
| reviewcap | sleep→eval | shared | cap |
| reviewsplit | sleep→eval | shared | split |
| rm-check2 | sleep→eval | shared | dissolve |
| rundesc | sleep→eval | shared | desc |
| runmode | sleep→eval | shared | mode |
| states | sleep→eval | shared | states |
| status | sleep→eval | shared | status |
| thread | sleep→eval | shared | thread |
| wisp | sleep→eval | shared | wisp |
| worldspace | sleep→eval | shared | world |
| staleremedy | sleep→eval | serveVerified | remedy |
| serving | sleep→eval | serveVerified | serving |
| reviewdraft | sleep→eval | serveVerified | draft |
| identity | sleep→eval | serveVerified | identity |
| filehead | sleep→eval | serveVerified | head |
| fileimg | sleep→eval | serveVerified | img |
| autogrow | sleep→eval | shared | grow |
| dreamfade | sleep→eval | shared | ghost |
| artifactwrap | sleep→eval | shared | wrap |
| beautycap | sleep→eval | shared | beauty |
| hfit | sleep→eval | shared | fit |
| marktab-geometry | sleep→eval | shared | geometry |
| markrail | sleep→eval | shared | rail |
| indtrace | sleep→eval | shared | trace |
| devoverlay | sleep→eval | own-sleep | overlay |
| posture | sleep→eval | own-sleep | posture |
| dashboard | sleep→eval | own-sleep | commits |
| motion | sleep→eval | own-sleep | commits |
| morph | sleep→eval | own-sleep | morph |
| morphhold | sleep→eval | own-sleep | morph |
| projtitle | sleep→eval | own-sleep | title |
| bdinput | sleep→eval | own-sleep | limit |
| dissolve | sleep→eval | shared | dissolve |
| dissolveperf | sleep→eval | shared | dissolve |
| optrace | sleep→eval | other | trace |
| reviewask | n/a | shared | (builds fixtures) |
| revieworder | n/a | own-poll | (port-0) |

## Flake evidence

- **subslog** — named in the #428 filing ("the guard suite fails under
  concurrent lanes and passes alone"). Render layer: shared server, so the
  server layer is harness-owned; the flake is `goto networkidle`+`sleep(1200)`
  before the first `__dwSubmissions()` read. Under load the client JS that
  defines `__dwSubmissions` and builds the `.qa` cards has not run when the
  sleep ends → `all()` resolves null → "the log is reachable … FAIL".
- **bdinput/posture/projtitle/dashboard/motion/morph/morphhold/devoverlay** —
  server layer: the `spawn`+`sleep(2500)` idiom is the exact #507 burndown/
  bdhover defect. Six of eight have no `try/catch` on the readiness `fetch`,
  so under load they throw `ECONNREFUSED` and report "threw before finishing"
  over a correct server. `posture` has no identity check at all.
- **markrail** — was the deterministic half of #507 (selector scope, not
  readiness); already fixed. Listed for completeness.
- The remaining `sleep→eval` shared-server guards have **no suite-failure
  naming** beyond subslog; their sleeps are generous (900–1200 ms) and the
  server layer is harness-owned, so their individual flake risk is low. They
  are the long tail of the same render shape and are deferred below.

## Conversion plan (this lane)

- **Convert (server layer):** the 8 own-sleep guards → `serveVerified`
  (drop-in: it spawns, polls, and identity-checks — replacing `spawn`+`sleep`
  + the hand-rolled fetch check). `devoverlay` passes `args:['--dev']` and its
  2nd `rsrv` server gets the same treatment.
- **Convert (render layer):** `subslog` (the named instance) → `waitFor`
  after `goto`. The 8 server guards also get a render `waitFor` gate (they
  share the `goto networkidle`+sleep render race), closing both layers as #507
  did for burndown/bdhover.
- **Defer (render long tail):** the ~40 remaining `sleep→eval` shared-server
  guards. Reason: server layer harness-owned (the acute #428 layer is closed
  by the 8 conversions); no suite-failure naming beyond subslog; generous
  sleeps; a per-guard `waitFor` sweep is mechanical and low-risk and is the
  natural follow-up lane. Each is listed above so the work is enumerable.

## Deferred-with-reason (render long tail)

The shared-server `sleep→eval` guards (qacard, reflow, headertravel,
headcrumb, history, note82, oneinput, pip83, plugcmd, prominence, qfade,
qfocus, qlinkpip, qorder, qroll, qsec, regroup, research, restcollapse,
reviewcap, reviewsplit, rm-check2, rundesc, runmode, states, status, thread,
wisp, worldspace, autogrow, dreamfade, artifactwrap, beautycap, hfit,
marktab-geometry, markrail, indtrace, dissolve, dissolveperf, optrace, and
the serveVerified-but-render-sleep guards qsignal/staleremedy/serving/
reviewdraft/identity/filehead/fileimg) are **deferred**:

- the server layer (the layer that throws under concurrent lanes) is either
  harness-owned (shared) or already `serveVerified`;
- their first reads sit behind 900–1200 ms sleeps that are ample for the
  client render at the loads recorded;
- none is named in a suite failure (#428 names subslog; #507 named
  burndown/bdhover/markrail — all converted);
- a blanket conversion of ~40 guards is a mechanical follow-up better done as
  its own lane than rushed here, and the brief explicitly allows
  deferred-with-reason.

This lane closes the **server** layer in full (all 8 own-sleep guards) and
the **render** layer for the named instance (subslog) plus the 8 server
guards' render gate. The remaining render shape is enumerable above and
named for a follow-up.
