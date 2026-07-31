# Lane 728 — the preflight's lane count broke silently and still read confident

**Verdict: LANDED.** The preflight now prints a real ccc lane count against
the live tree, and a future `discover_lanes` arity change fails a test rather
than degrading to a confident verdict on load alone.

## What the deliverable's real surface looked like

**BEFORE** (the bug, reproduced live against the live tree at the start):

```
guard preflight: WRONG-ANSWER-RISK [load 32.21 (2.0x cores) on 16 cores, ? (ccc-only; #675) ccc lane(s)] — WRONG-ANSWER regime: a browser guard can die before judging (#666/#471). Run a subset (DREAMWORK_GUARDS=<name>) or force with DREAMWORK_GUARDS_FORCE=1 — the verdict will carry this fact
```

`? (ccc-only; #675) ccc lane(s)` beside a confident `WRONG-ANSWER-RISK`.
#606's whole design argument was that load AND lane count **compose** —
"the lane count is the actionable lever the coordinator controls (wait for
the fleet), load is what actually breaks the guard". Half that instrument
was gone while it read as operational. Load was 32.21 — exactly the
structural-break point the instrument exists to refuse on — while the
coordinator ran the guard suite, which is itself the finding the brief
named.

**AFTER** (rebased onto local master, quoted against the live tree):

```
guard preflight: OK [load 23.31 (1.5x cores) on 16 cores, 4 ccc lane(s)] — guards should judge honestly
```

`4 ccc lane(s)` — a real count. Load has fallen to 23.31 (below `LOAD_OK`)
because the coordinator's guard suite finished in the interval, which is the
brief's "load samples at START" observation made visible: a run that began at
24 (OK) was executing at 34 (RISK) a moment earlier, and a run beginning now
would judge honestly again.

## What I changed and why

### 1. A named accessor over `discover_lanes` — `status_sync.live_lane_count(target)` (#440)

The brief's item 1, and #606's own out-of-scope note recommended exactly this:

> "status_sync.py is the right place for a lane-count accessor if a second
> caller ever needs it — guard_preflight.py re-derives the main-checkout path
> and calls discover_lanes directly. Once #675 lands and exposes a clean
> accessor, the preflight should call that instead."
> (commit `8d88e2d9`, #606 instrument commit body)

#675's lane made the same recommendation. `live_lane_count` pins the arity
contract in **one** function:

```python
def live_lane_count(target: Path) -> int:
    found, _phantoms, _agent_tool = discover_lanes(target)
    return len(found)
```

The next arity change breaks ONE line (this one) rather than N positional
callers — #440's one-supported-way rule. `count_lanes` now calls
`live_lane_count`, never `discover_lanes` directly.

### 2. NARROW THE EXCEPT (item 2 — the one the brief cares about most)

This is the deeper defect. The original `count_lanes`:

```python
    try:
        found, _phantoms = status_sync.discover_lanes(t)
    except Exception:        # ← caught EVERYTHING
        return None
```

A bare `except Exception` turned a hard INTERFACE BREAK (the ValueError from
a 2-tuple unpack of a 3-tuple) into a soft "I could not see" (#728's words).
#136 says those are different facts:

> "- **#136** — A questions.md that parses to nothing must say so … a file
>   the reader cannot see is one /answer cannot write"
> (`dev/ledger.py get 136`)
> "/proc is unreadable on this host" is a legitimate unknown; "the function
> I call changed shape underneath me" is a bug that must be loud.
> (#728 task entry)

The narrowed form catches only what `/proc` can actually raise, and lets a
contract mismatch propagate:

```python
    try:
        return status_sync.live_lane_count(t)  # #440: accessor, not a unpack
    except OSError:
        # /proc unreadable on this host — a legitimate unknown (#136).
        return None
    # TypeError/ValueError (a contract mismatch) is deliberately NOT caught —
    # see docstring. main() renders it as COUNT-BROKEN so the break is loud
    # rather than a silent '?'.
```

### 3. What the preflight PRINTS when it cannot count

The brief flagged the paper-over: "`?` beside a confident verdict is #671's
shape". Two distinct outputs now:

- **`/proc` unreadable (OSError → None, a legitimate unknown):** the render
  names the count unavailable and the recommendation says the verdict rests
  on load alone — it does NOT classify on load alone as "no fleet", which is
  the trap the brief warned against:
  ```
  guard preflight: CAUTION [load 28.00 (1.8x cores) on 16 cores, ? (ccc-only; #675; count unavailable) ccc lane(s)] — load in the measured grey zone; lane count unavailable, so whether a fleet is out is UNKNOWN — verdict on load alone, treat the fleet lever as unreadable
  ```
- **Contract break (TypeError/ValueError, a bug):** `main()` catches it and
  prints a `COUNT-BROKEN` line that names the error type and marks the
  verdict as standing on one leg — distinct from the `?` of an unreadable
  `/proc`:
  ```
  guard preflight: COUNT-BROKEN WRONG-ANSWER-RISK [load 38.00 on 16 cores, lane count UNAVAILABLE: ValueError: not enough values to unpack (expected 3)] — the lane-count accessor's contract broke (#728); verdict rests on LOAD ALONE, the count half is gone (#606)
  ```

### 4. A test pinning the arity contract (item 3)

`test_status_sync.py` gains two tests at the end:
- `test_live_lane_count_returns_an_int` — the accessor returns an int, 0 for
  an empty target.
- `test_discover_lanes_arity_is_three` — **the discriminating assertion**:
  `discover_lanes` returns exactly three elements. Catches what the accessor
  cannot: a future fourth field would keep the 3-unpack silently working, so
  this test guards the arity the accessor reads.

`test_guard_preflight.py` gains `TestCountLanesExceptNarrowing` and
`TestCountBrokenRender`:
- `test_proc_unreadable_returns_none_not_raises` — OSError → None.
- `test_contract_break_propagates_not_swallowed` — ValueError propagates
  (reintroduce `except Exception` and THIS reds — it's the one that pins the
  narrowing; the OSError test alone cannot).
- three COUNT-BROKEN render assertions.

## Red-proof, both directions (quoted)

### Direction 1 — inject the real defect, watch the discriminating test go red

**Injected:** widened `except OSError` back to `except Exception` in `count_lanes`
(via `dev/redproof.py begin/restore`). **Result — the discriminating failure:**

```
FAILED test_guard_preflight.py::TestCountLanesExceptNarrowing::test_contract_break_propagates_not_swallowed
  Failed: DID NOT RAISE <class 'ValueError'>
```

The OSError test (`test_proc_unreadable_returns_none_not_raises`) **passed**
under the sabotage — which is correct, because widening the except to
`Exception` still catches OSError. The narrowing is pinned by the ValueError
test, not the OSError one; that asymmetry is the point.

### Direction 2 — the composition link, and a constructed false-green

**Risk identified:** `test_contract_break_propagates_not_swallowed` patches
`live_lane_count` to raise — so it proves `count_lanes` propagates a raise,
but it does NOT prove a *real* `discover_lanes` arity change would make
`live_lane_count` raise in the first place. That link is the composition:
`count_lanes → live_lane_count → discover_lanes`. If any hop were bypassed,
the test would pass green over a real bug.

**Proved by changing the real production line** (via `dev/redproof.py
begin/restore`): reverted `discover_lanes` to a pre-#675 2-tuple return.
**Result:**

```
=== Does a real arity change reach live_lane_count (the composition link)? ===
RED (expected): live_lane_count raised ValueError: not enough values to unpack (expected 3, got 2)

FAILED test_status_sync.py::test_discover_lanes_arity_is_three
  AssertionError: discover_lanes arity changed; live_lane_count and the test suite
  need updating together (was 2-tuple)
  assert (True and 2 == 3)
FAILED test_status_sync.py::test_live_lane_count_returns_an_int
  ValueError: not enough values to unpack (expected 3, got 2)
```

The link holds end-to-end: a real arity change (1) makes `live_lane_count`
raise `ValueError`, (2) propagates through `count_lanes` to `main()` (because
the except is narrowed), and (3) reds two tests on the right message. The
discriminating message `was 2-tuple` is the contract break named.

**One false-green named, not closed:** the brief's Direction 2 candidate —
"an Agent-tool-only fleet: count is now non-zero via #675 but they are not
`ccc`; does the label still say `ccc lane(s)`?" — is #727 (open, live, out of
scope). The preflight's label reads `ccc lane(s)` and `live_lane_count`
returns only the `ccc` arm of the 3-tuple, so an Agent-tool-only fleet
reports 0 lanes under a label that says `ccc`. That is #727's defect (the
label went stale when the count got honest), not this lane's. Reported, not
built.

## Red-proof gate

```
$ python3 dev/redproof.py check
history: examined 2 commit(s) since 1ab60a3c8633 (master) against 2 injected path(s); read 4 blob(s), 0 holding a recorded injection.
check: clean — 2 injection(s) registered, all restored and absent from the working tree and from this branch's commits:
  dev/guard_preflight.py (sha 3323d0d38dee, hint: 'except Exception:')
  status_sync.py (sha a13cb4e14685, hint: '# SABOTAGE for #728 red-proof Direction 2: revert to pre-#675 2-tuple.')
```

**Clean.** Both injections restored, no sabotage in the branch's commits.

## Verification

- `python3 -m pytest test_guard_preflight.py test_status_sync.py` — **69 passed**
  (both suites, post-rebase).
- `python3 lint.py` — **clean (6 warnings)**, no ERRORs; the 6 are the
  expected ledger-store-can't-travel-in-a-worktree WARN that fires in every
  worktree.
- `python3 dev/guard_preflight.py` against the live tree — quoted above
  (before: `?`; after: `4 ccc lane(s)`).

**Off-limits observed:** did not bind guard ports, did not run browser guards,
did not run `just guards` (the coordinator's suite was live; load was ~34 at
the start). Limited test threads. No off-limits files touched (lint.py,
dev/redproof.py, briefs/boilerplate.md, watch.py/client/, justfile all
untouched).

## Cited issues, each opened and quoted

- **#728** — this task. "`guard_preflight.py:128` unpacks a 2-tuple; `#675`
  made `discover_lanes` return 3. The `ValueError` is swallowed by a bare
  `except Exception: return None`."
- **#606** — the instrument. Its out-of-scope note predicted this exact break:
  *"status_sync.py is the right place for a lane-count accessor if a second
  caller ever needs it … guard_preflight.py re-derives the main-checkout path
  and calls discover_lanes directly. Once #675 lands and exposes a clean
  accessor, the preflight should call that instead."* (commit `8d88e2d9`)
- **#675** — the arity change. "`status_sync.py:306 def discover_lanes(target)
  → (found, phantoms, agent_tool)`". This lane adds the accessor it
  recommended.
- **#136** — "a file the reader cannot see is one /answer cannot write";
  applied here: "/proc unreadable" and "function changed shape" must render
  differently.
- **#671** — "a check that examined nothing must not read as passing"; here,
  half a check (`?` beside a confident verdict).
- **#440** — the one-supported-way rule; this lane adds `live_lane_count`
  rather than another positional unpack.
- **#727** — open; the `ccc lane(s)` label is now stale for Agent-tool-only
  fleets. Reported, not built (out of scope).

## Rebase outcome

Rebased onto **local master** (`git rev-parse master` → `7ead8f77`, which was
4 commits past my branch base `1ab60a3c` — master moved while I worked). The
rebase applied cleanly with no conflicts. No `<<<<<<<`/`=======`/`>>>>>>>`
markers remain (swept with the anchored `={7}$` form). Branch now:

```
a83d8f83 test(#728): pin the arity contract and the narrowed except
71b58c0b fix(#728): narrow the lane-count except and route through a named accessor
```

Working tree clean (only untracked `BRIEF.md`).

## Out of scope — recommend a task, did not build

**The load-samples-at-START timing gap** (the brief's explicit ask). The
preflight reads load once at the top of `just guards`, then the guards run
for minutes under a fleet the preflight did not re-measure. I observed it
live: the preflight read 32.21 (RISK) while the coordinator's suite was
mid-run; by the time I re-quoted it, load was 23.31 (OK) with the suite done.
A run that *began* at 24 (OK) could *execute* at 34 (RISK) — the verdict
labels the start, not the regime the work actually runs in.

**Recommend: a task to re-sample load mid-run (or at least re-print the
preflight on the summary line, which the forced-run path already does).**
Not built — the brief said recommend, not build, and it touches the justfile
(off-limits here).

## Dogfood report

- **The brief was right and specific.** It named the one stale caller
  (`guard_preflight.py:128`), confirmed the others were updated by #675, and
  pre-decided the accessor form — so I did not re-derive any of it. The
  "item 2 is the one I care about most" framing correctly steered me to
  spend the design effort on the except and the output contract, not the
  unpack.
- **`dev/redproof.py check` is the right gate.** The "examined N commits
  since base, 0 holding a recorded injection" line is a load-bearing
  guarantee I did not have to take on faith — it scans the actual blobs. It
  caught nothing here (I restored both), but the *presence* of the scan is
  what made the red-proof trustworthy rather than theatrical.
- **One friction point:** `dev/redproof.py` snapshots the file *as committed
  at the moment of `begin`*. Because I committed the fix BEFORE arming the
  injection, `restore` returned the fixed file — which is correct and
  documented (#608), but it means I had to verify the fix was back by grep
  after each restore rather than trusting the tool's "restored" message.
  This is documented behavior, not a bug; noting it because the alternative
  (snapshot the pre-fix file) would have silently undone the fix.
- **The anchored `={7}$` conflict-marker sweep** worked: no false positives
  on this repo's prose, which discusses `=======`-shaped dividers in
  `lessons.md`. Worth the `$`.
