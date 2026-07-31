# Lane 631 report — session-log landing sequence

## Verdict

PASS. The canonical design now ends in a 15-increment landing sequence, and
increment 1 is implemented because it is genuinely independent: its wire model
has no production caller, changes no served asset, starts no thread, opens no
store and cannot affect the dashboard.

Post-rebase deliverable commits:

- `34208dcd` — `feat(#631): define the session log wire model`
- `43249603` — `design(#631): sequence the session log landings`

The branch was rebased onto local master `45eb6c202d7982dbe09fde74537383f97d768fae`
before this report. The rebase completed without conflicts. The final branch
tip including this report is the report commit itself; the coordinator should
use `git rev-parse cx-631seq` rather than a pre-report sha.

## What changed

- Appended `## 12. Numbered landing sequence` to
  `.dreamwork/docs/plans/session-log-view.md` rather than creating a second
  plan. Every increment names its files, live callers/test harnesses, a check
  that can actually go red, the discriminating failure, and what remains.
- Put the derived cache at increment 10, after the database core's
  other-store/raw-connect guard prerequisite. The API works from memory first,
  so the cache is an optimization and stays safe to be wrong about.
- Put every notification/store substrate measurement on a real-disk,
  lane-private cache fixture. A `/tmp` result is explicitly inadmissible.
- Confirmed the component mount from the current tree: the native build entry
  registers the production Research component, the router resolves registered
  authorities through `dwNative.registry`, and `watch.py` embeds the native
  bundle. The sequence does not rely on the brief's assertion alone.
- Added `session_log/model.py`, its public package surface and
  `test_session_log_model.py`. The model closes the node/state/event
  vocabularies, validates source ranges, omits unmeasured optional fields and
  serializes the exact `{ev, node}` wire shape.
- Found and sequenced one hidden HTTP seam: `POST /session/watch` must be
  origin-gated but dispatched outside `WRITE_ROUTE_HANDLERS` and before journal
  receipt creation. Otherwise registering a read watcher would silently become
  a new durable write route.

## Verification

- `just pytest test_session_log_model.py` — **10 passed**.
- `python3 lint.py` — **clean, 6 warnings**, exactly the worktree bar. The six
  are the expected worktree/live-state warnings: three answered questions
  without dates, absent ledger, absent status, zero-entry marker examination,
  the pre-existing lesson near-duplicate, and ledger checks examining nothing.
- `python3 dev/redproof.py check` — **clean**: 2 injections registered, both
  restored; 2 branch commits and 2 blobs examined; 0 contained an injection.
- `git diff --check` — clean before the sequence commit.
- No browser guard, server, port bind, full pytest suite, live-ledger mutation,
  push, merge, or notification utility was used.

## Red-proof evidence

### Direction 1 — the actual wire defect goes red

Injection: `SourceRef.to_wire()` emitted Python's `length` spelling instead of
the designed JSON `len` spelling. The injected source was read back before the
test. The focused check failed at the intended assertion with:

> `source ref must spell its wire length field 'len', not expose the Python attribute name`

The diff named `{'length': 121}` versus `{'len': 121}`. This was a semantic
wire failure, not an import/setup failure. `dev/redproof.py restore` restored
and verified the fixed file.

### Direction 2 — the happy-path proof has a real false-green, now closed

Injection: disable node-kind validation while leaving serialization intact.
The exact happy-path wire test stayed green (**1 passed**), demonstrating that
a correct-looking fixture does not prove the vocabulary is closed. The sibling
closed-vocabulary check then failed only the malformed-kind case:

> `Failed: DID NOT RAISE <class 'session_log.model.ModelError'>`

with the other three parameter cases still green. That is the discriminating
shape: serialization and unrelated validators continue working while the
unknown kind crosses the boundary. The injection was restored and the final
10-test run passed.

## Relied-on issue readings

- **#631:** *"Scope: the standardised node/event model, the
  session-index.sqlite3 bookmark cache (derived, NOT the ledger store), the
  four read routes behind the existing confinement gate, the SessionWatcher
  seam, and the SessionLog component."* This is the completeness checklist
  used for the 15 increments.
- **#634:** *"Its FIRST TWO PROBES SAID THE DEFECT DID NOT EXIST ... They ran
  in the session scratchpad under /tmp ... The lane caught it and re-ran on
  real disk, where the answer was 15/15 YES."* This is why increments 7, 9,
  10, 11 and 14 reject tmpfs evidence.
- **#645, increment 5:** *"Route Journal, replay and consume connections
  through the core with their existing domain APIs unchanged; enable the
  no-production-raw-connect guard. The standing rule is real before the first
  new schema depends on it."* This is the hard prerequisite named by the late
  session-index increment.

## Rebase and scope

The lane started from the dispatched base `377da328becc506bd64dc165d958e773ee69b063`.
It rebased once before editing onto `87d7481674ba6b66f637cdfd53d537ddb014453f`
and again at handoff onto `45eb6c202d7982dbe09fde74537383f97d768fae`.
Neither rebase conflicted. The second rebase rewrote both deliverable shas, so
the design's increment-1 receipt was updated after the rebase rather than
leaving a dead pre-rebase sha.

No unflagged contradiction was found between `BRIEF.md` and the current lane
boilerplate. `BRIEF.md` remains untracked coordinator input and was not
committed.

## Out of scope

`test_file_notify.py` currently builds its inotify fixture from pytest's
`tmp_path`, which is normally under `/tmp`. Its existing normal-write checks
are not evidence that the mmap/mtime hazard reproduces there, and this lane did
not change or run that suite. It is nevertheless a dangerous example for a
future SessionWatcher lane to copy. The sequence counters that locally by
requiring a real-disk fixture; a broader audit or shared real-disk pytest
fixture should be filed separately if the coordinator wants the existing
watcher suite brought under the same substrate rule.

## DOGFOOD REPORT

Two useful frictions surfaced beyond the named deliverable:

1. The design's phrase "POST because it changes server state" hides a live
   architectural trap in this repository: normal POST dispatch is the durable
   write/journal path. Without tracing `make_handler` and the write-route
   harness, a straightforward implementation would make `/session/watch`
   create a journal receipt and mutate the target while still looking like it
   followed the four-route design. The landing sequence now names both the
   bypass and the test that keeps the write-route set unchanged.
2. The repository's own notification tests make `/tmp` look like the natural
   fixture substrate at exactly the moment this task says that substrate can
   answer filesystem questions confidently wrong. The task-specific warning
   was excellent, but a future brief should point to a named real-disk fixture
   helper rather than only saying where not to measure. Until such a helper
   exists, each watcher lane has to invent cleanup and isolation again.

No other loop-tooling friction or brief/boilerplate conflict was found.
