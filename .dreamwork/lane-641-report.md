# Lane-641delta — #641 PHASE 1: the delta, on the transport we already have

## Verdict

**LANDED.** `GET /data.json?since=<v>` returns a derived per-key delta (or a
304-shaped "no change" sentinel, or the full document for any mismatch).
Client consumes it via `applyDataResponse` and self-heals on `check`. The
2s poll remains the fallback; a client that never sends `since` sees today's
endpoint byte-unchanged.

- **server**: 73 non-comment lines in `watch.py` (budget: 60–90 ✓)
- **client**: 30 non-comment lines in `client/router.js` (budget: 30–40 ✓)
- **rebase**: clean onto local master (7ead8f77), no conflicts

## What changed and why

### Server (`watch.py`)

`compute_delta(prev, nxt)` — derived per-key delta between two `collect()`
outputs, compared by serialized equality (`json.dumps(..., sort_keys=True)`),
`generated` excluded. Changed keys shipped whole; removed keys listed. This is
the plan's "## The trap" made code: the delta is a generic function of two
outputs of the one authority, so nothing downstream can drift from `collect()`.

`apply_delta(base, delta)` — the inverse, used by the born-red test.

`derived_check(doc)` — SHA-256 of the document with `generated` excluded, so a
client can self-verify its reconstruction.

`_data_json_cached(target, burn_step)` — document cache keyed by `(target,
burn_step)`, retaining `(version, doc, prev_version, prev_doc)`. One `collect()`
per real change instead of one per window per tick; the previous build is kept
so a client one version behind gets a real delta. `BURN_STEPS` is a closed set
of 5, so the cache is bounded.

`_data_json_response(entry, since)` — the three-case decision: `since`==
current → `{"v", "unchanged": true}` (#136 distinct sentinel); `since`==
prev_version → `{v, base, changed, removed, check}`; anything else (or no
`since`) → full document. "Full is always the safe answer."

The `/data.json` route now calls these; a request with no `since` is
byte-identical to the prior `collect(target, burn_step=burn_step)` path.

### Client (`client/router.js`)

`lastDataV` global tracks the version (watched_mtime) of the doc held.
`dataJsonUrl()` appends `&since=<lastDataV>` when set (null → no param → full).
`applyDataResponse(j)` routes the response: `unchanged` → null (skip
re-render); `changed` present → apply delta (delete removed, overwrite changed);
full doc → pass through. `cycleBurnStep` resets `lastDataV` (different burn_step
= different bucketing, cached base is stale).

### Tests (`test_watch.py`)

`TestDataJsonDelta` — 6 tests:
1. **Reconstruction round-trip** (the discriminating test) over 5 adversarial
   pairs: key added, key removed, nested mutation, generated-only, two-key
   change. Each asserts `apply(base, delta(base, next)) == next` (minus
   `generated`), with a runtime precondition that the case actually differs.
2. **generated excluded** from delta and check.
3. **no since → full document** (revert story).
4. **since==current → no-change sentinel** (#136 distinct).
5. **unknown since → full document** (safe fallback).
6. **live cache path** returns a delta that reconstructs byte-for-byte against
   the actual `_data_json_cached` + `_data_json_response` machinery.

Updated the `test_live_data_assignments_go_through_one_seam` guard: the three
fetchers now route through `applyDataResponse` before `setData`, so the
assertion matches `applyDataResponse(await` (×3) instead of `setData(await`.

### Docs (`file-formats.md`)

Added a `/data.json?since=<v>` contract section documenting the three response
shapes and the reconstruction guarantee.

### Dist rebuild

`just build-client` ran clean; idempotent (second run produced identical
hashes); `lint.py` dist guard satisfied (0 ERRORs).

## Red-proof — both directions

### Direction 1 (injection → discriminating red)

Sabotaged `compute_delta` to skip the `tint` key (a genuinely-changed key),
via `dev/redproof.py begin/restore`. The reconstruction test went red on the
discriminating message:

```
SUBFAILED(case='two-key change')
AssertionError: {'target': '/y', 'git': {'sha': 'ccc'}, 'tint': 'blue', 'open_questions': 5}
  != {'target': '/y', 'git': {'sha': 'ccc'}, 'tint': 'red', 'open_questions': 5}
  : case 'two-key change': reconstruction diverged from target —
    delta was {changed: ['git', 'open_questions', 'target'], removed: []}
```

The failure names the key (`tint`), the byte difference (`blue` vs `red`), and
the case — and the delta envelope printout conspicuously omits `tint` from
`changed`. Restored; `redproof check` clean.

### Direction 2 (delta correct, client still wrong — named, not closed)

The JS `applyDataResponse` is a **second implementation** of the Python
`apply_delta` — the classic two-descriptions hazard. The reconstruction test
exercises the Python side; the JS side is verified by static reasoning (traced
the removed-key case: empty `changed` object is truthy in JS so the delta
branch is entered; `removed` keys are deleted; logic is correct). A browser
guard or JS unit test would close this definitively; I did not run one (load
~24, brief authorizes a static probe instead, and the Python reconstruction
test is the load-bearing proof).

**Named open cases:**
- **Two changes within one watched_mtime tick**: if two writes happen but
  `watched_mtime` doesn't advance, the cache returns the same document and the
  second change is invisible until the next advance. This is a property of
  `watched_mtime`'s resolution, shared with the full-document path — the delta
  doesn't make it worse.
- **`since` from before a server restart**: the cache holds only the current +
  previous build, so a `since` older than that falls back to full (correct —
  "full is always the safe answer").

## Cited issues (relied-on lines)

- **#641** (open): *"the load-bearing unknown is already VERIFIED rather than
  inferred: a probe streamed SSE from stdlib ThreadingHTTPServer to real
  Chromium, held concurrency, and auto-resumed via Last-Event-ID with zero
  client reconnect code."* — SSE approved, phase 1 is the delta on the poll.
- **#612** (landed): the line-budget precedent — *"longest quoted field 4568
  -> 200 chars"*; volume matters, the fewest lines that carry the meaning.
- **#136** (landed): *"THREE zero-states, not one"* — "no change" and "I could
  not compute a delta" must not render identically. The `unchanged` sentinel is
  distinct from both the delta and the full document.
- **#608** (landed): *"snapshot the FIXED file, the state you must END on"* —
  redproof snapshots the post-fix file; restore returns the fixed state.
- **#620** (landed): *"a suffix, not the two names the #614 plan proposed"* —
  `WATCHED_MTIME_IGNORED_SUFFIXES = ("-shm",)` at watch.py:4068 @ dc739001; phase 0 is done.

## Verification (run, with load)

- **`python3 -m pytest test_watch.py -k "DataJsonDelta or Collector or Summary
  or summary_route or live_data or AppShell or QuestionRoute or ViewRoutes"`**
  — **276 passed, 0 failed** (8 subtests passed). Load 23.82.
- **`python3 -m pytest test_watch.py::TestDataJsonDelta`** post-rebase —
  **6 passed, 5 subtests passed**.
- **`python3 lint.py`** — **0 ERRORs**, 6 WARNs (expected in a worktree: store
  WARNs per #611, near-dup lessons first-sentence).
- **`node --check client/router.js`** — OK.
- **`just build-client`** — clean; idempotent (identical hashes on re-run).
- **No browser guard run** (load ~24; static reasoning on the JS path is the
  authorized substitute; the Python reconstruction test is the proof).

## Out of scope (named, not fixed)

1. **The JS `applyDataResponse` is a second description of `apply_delta`** —
   a JS unit test or browser guard would close the two-descriptions gap for the
   client side. Filed for the coordinator.
2. **Phase 2 (the SSE push channel)** is a separate dispatch — this lane is
   phase 1 only.
3. **`dreamhub.py` adoption** of `?since=` — same contract, its own increment.

## Dogfood report

1. **The brief's `BRIEF.md` line-budget steer was right and caught a drift.**
   My first server draft was 159 lines (a history ring of 8 snapshots). The
   "past double that, STOP and report" rule forced a refactor to 73 — the plan
   only needs the immediately-prior build, and the ring was speculative. Good
   rule, it worked.
2. **The `setData(await` seam guard (`test_live_data_assignments_go_through_one_seam`)
   broke immediately** when I wrapped the three fetchers. The guard's *intent*
   (every fetcher goes through setData) survived, but the literal string
   changed. I updated the assertion to match `applyDataResponse(await` — but a
   guard that pins a literal string is a guard with an expiry date the moment
   the seam moves one layer. Consider asserting the structural property
   ("every `fetch('/data.json` call is followed by `setData` within N lines")
   rather than a frozen token.
3. **`just build-client` blocked on esbuild postinstall** (`npm warn
   install-scripts blocked`). It still produced correct output, but the warning
   is noisy and a fresh checkout might behave differently. Worth a note in the
   build docs.
4. **The brief was accurate throughout.** Phase 0 done (#620), SSE approved
   (#614), the trap section was exactly where cited, the line budget was
   binding. No stale facts cost me time.
