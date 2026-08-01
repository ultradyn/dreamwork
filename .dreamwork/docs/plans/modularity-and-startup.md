# Modularity and startup: make the decision measurable (#368 / #124)

## Decision to put to Max

Should #368 absorb #124 and become **one demand-driven extraction programme**, with a
measured startup contract, or should both be closed because the client extraction has
already removed the mass that motivated the breakup?

**Recommendation:** absorb and re-scope them. Do not break up `watch.py` as a project.
Keep `watch.py` as the compatibility entry point and extract one stable application seam
only when a named consumer such as `dreamhub` needs it. Adopt, provisionally, a
`version`-style warm-page-cache breakpoint of **p95 <= 100 ms end to end** and
**target-minus-interpreter p50 <= 60 ms** on this host. Ask Max to accept or replace
those two breakpoints before anyone argues for a compiled core.

That is a concrete yes/no decision. If he accepts it, the next extraction must name its
consumer and prove the benchmark stays inside the contract. If he rejects it because
the desired p95 is below roughly 50 ms, the compiled-core experiment has a measurable
reason to exist. No refactor is authorised by this document.

## The corrected premise

At `beddf975`, measured in this worktree on 2026-08-01:

- `watch.py` is **6,267 lines**, not 15,563 and not the ledger note's later 6,255.
- The eight source files under `client/` total **11,390 lines**: 1,974 CSS, 9,159
  JavaScript, 148 favicon, and 109 HTML lines. The large CSS/JS literals have already
  left Python.
- `watch.py` still has 148 top-level functions and five classes. Those definitions
  occupy 4,756 lines. Its largest remaining unit is the 1,227-line `make_handler`, so
  the file remains broad, but it is no longer a 15k-line mixed Python/client monolith.
- `dreamwork_db/` is the existence proof for a deeper module: a 378-line connection and
  transaction policy core; separate task, question, and review repositories; migration
  and question parsing modules; and one package API that does not expose raw SQLite.
  Domain repositories depend inward on `core`, while callers receive repositories
  through `StoreSpec` and `open_database`.

The old line-count premise is about 60% too high. Starting a broad split from it would
optimise a codebase that no longer exists.

## What the startup benchmark measures

Run:

```text
python3 dev/startup_benchmark.py watch --runs 40 --warmups 5
python3 dev/startup_benchmark.py dreamwork_db --runs 40 --warmups 5
```

The target imports the module and returns a trivial value, modelling a `version` verb
whose useful work is negligible. Each **fresh-process** sample starts a new Python
interpreter, so `sys.modules` cannot leak between samples. A paired control starts the
same interpreter and prints the same sentinel without importing the target. Pair order
alternates to reduce directional drift. The **warm-import** distribution imports once in
one interpreter and repeats only the trivial lookup.

Environment: Python 3.14.6, Linux 7.1.3 x86-64. The snapshot ran at load averages
38.14/33.48/29.76, with 49 GiB of 60 GiB swap used. Load average includes blocked tasks,
so it is context, not a CPU-contention diagnosis.

| Target | first observed | fresh p50 | fresh p95 | interpreter p50 | target - floor p50 |
|---|---:|---:|---:|---:|---:|
| `watch` | 175.077 ms | 153.179 ms | 177.783 ms | 16.400 ms | 136.779 ms |
| `dreamwork_db` | 71.148 ms | 65.442 ms | 83.530 ms | 18.359 ms | 47.083 ms |

The warm-import lookup was below 0.001 ms p95 for both targets. That number is not a
startup claim; it shows that almost all observed cost is interpreter startup plus import,
not returning the version value.

The benchmark therefore says three useful things:

1. A version path that imports today's `watch` graph fails the proposed 100 ms p95.
2. The already-modular DB seam passes it in this snapshot. Python is not yet refuted by
   the measured startup claim.
3. A compiled replacement is justified by startup only if Max's real breakpoint is
   tighter than the Python floor plus a deliberately small import graph. “Faster” alone
   does not decide that.

### Controls and the open false-green

The harness refuses if the target exits non-zero, emits the wrong sentinel, or yields the
wrong sample count. Its tests also prove that fresh samples re-import a side-effecting
module while warm samples import it once, and that interpreter cost is reported and
subtracted.

It does **not** evict or observe the kernel page cache, pin CPUs, freeze CPU frequency,
or isolate scheduler noise. “First observed” means only the first child started by this
invocation; another process or an earlier run may already have warmed every relevant
page. Thus a disk-reading import can produce a plausible warm-cache distribution that
this tool cannot identify as OS-cold or OS-warm. The report names that state
`uncontrolled` and deliberately uses **fresh process**, not **cold cache**. A real
OS-cold claim needs a separate privileged/cache-observing protocol on a quiet host.

The brief associates this limitation with #702, but the actual #702 entry is about
`status.json` lane bookkeeping: *“The coordinator writes dispatches into
status.json['lanes'] ... status_sync.live_lanes reads status.json['dreamers'] ... Nothing
connects them.”* It contains no benchmark or page-cache principle. This document does
not use it as authority for the startup limitation.

## Rival boundaries, judged with IGC

**Context:** the client is already in real files; `watch.py` remains a broad Python
adapter; `dreamhub` is the named prospective consumer; and compatibility paths must keep
working while any extraction lands.

| Idea | All | G1 | G2 | G3 | G4 |
|---|:---:|:---:|:---:|:---:|:---:|
| A. Close both tasks; keep `watch.py` intact | ✘ | ✔ | ✘ | ✘ | ✔ |
| B. Big-bang layered breakup now | ✘ | ✘ | ✔ | ? | ✘ |
| C. Demand-driven seam behind compatibility facade | ✔ | ✔ | ✔ | ✔ | ✔ |

- **G1:** existing `watch.py`, deploy, and import paths remain valid throughout.
- **G2:** a named second consumer can reuse application behaviour without importing the
  HTTP server adapter or copying an implementation.
- **G3:** a version-style path meets p95 <= 100 ms and target-minus-floor p50 <= 60 ms
  on this benchmark host.
- **G4:** no speculative movement occurs before a consumer demands the seam.

Decisive errors:

- **A / G2:** keeping all application behaviour in `watch.py` leaves `dreamhub` choosing
  between importing the whole adapter and creating a second truth.
- **A / G3:** importing `watch` measured 177.783 ms p95, so the obvious version path
  fails the proposed breakpoint. A separate lightweight metadata leaf could fix startup,
  but would not solve G2.
- **B / G1:** moving 148 functions across several modules at once has no compatibility
  proof between increments; the migration itself becomes the product risk.
- **B / G4:** most proposed boundaries have no named consumer today, so the movement is
  speculative. **B / G3 remains unknown** because file count does not determine import
  graph; a badly layered package can remain just as expensive to import.
- **C / contested G3:** this passes only if the version entry imports metadata alone and
  ordinary CLI verbs import no more than the application/core seam. The measured
  `dreamwork_db` path is the evidence that the breakpoint is currently reachable, not a
  guarantee that every future extraction will preserve it.

One option survives all four goals: C.

## Proposed boundaries if Max chooses C

These are dependency rules, not a request to create directories now:

1. **Compatibility/entry adapters:** `watch.py` remains executable and import-compatible.
   A CLI entry owns argv, exit codes, stdout/JSON, and a tiny metadata leaf for `version`.
2. **Application core:** ledger projections and domain commands expose typed data and
   explicit results. They know neither HTTP handlers nor argparse. `watch` and `dreamhub`
   may both call them.
3. **Persistence:** `dreamwork_db/` remains the one connection/transaction door, with
   domain repositories bound through `StoreSpec`. The application core depends on its
   public API, never raw SQLite.
4. **Web adapter:** request authority, routing, response serialization, and client-asset
   serving stay outside the core. The current `make_handler` region is the eventual
   adapter boundary, but it moves only around a concrete consumer/test seam.
5. **Replacement seam:** the durable boundary for a later compiled core is the CLI/data
   contract—argv, JSON/stdout, exit status, and persisted schema—not Python function
   signatures.

The first extraction should be the smallest application operation that `dreamhub`
actually needs. Its acceptance test must call the same core operation through both
adapters. That makes reuse, testability, and startup measurable in one increment.

## Cost of the recommendation

Demand-driven extraction does not maximise immediate parallel write capacity. Until a
specific region moves, `watch.py` still has one writer, and compatibility wrappers add a
temporary layer. The gain is that each cost is paid only when a second consumer proves
the boundary. The alternative pays migration and import-cycle risk up front for seams
whose APIs have not yet been discovered by use.
