# Lane report — #718: three fleet counters, two frozen

## Verdict

Two of the three counters read the **same hand-maintained field** (`status.json["lanes"]`),
which has **no automatic writer and no automatic pruner**. They froze because nobody updated
it across five dispatches. The third (`ccc-live`) reads `status.json["dreamers"]`, which
`status_sync` prunes automatically every tick — so it tracks reality. The fix lives entirely
in `tick_line.py` (labels + a falsified docstring claim); it does not require `status_sync.py`
or `dev/ledger.py`.

## What feeds each counter

`_fleet_fact` (`tick_line.py`) reads ONE `status.json` and derives all three:

| counter | source field | writer | automatic pruner |
|---|---|---|---|
| `lanes N recorded` | `status.json["lanes"]` | coordinator, by hand | **none** |
| `runners ccc N` | `status.json["lanes"]` (same list) | coordinator, by hand | **none** |
| `N ccc-live` | `status.json["dreamers"]` via `status_sync.live_lanes` | coordinator, by hand | **`status_sync` every tick** |

`status_sync.DERIVED = ("queue", "current_task_ids", "dreamers")` — `dreamers` is owned and
pruned by the sync tool (dead processes removed, landed tasks reaped, on every run). `lanes`
is **not in `DERIVED`**: it is author-owned prose that no tool writes, appends to, or removes
from. `grep -n "dreamers\|lanes" dev/ledger.py` returns nothing — the dispatch tooling writes
neither field.

So `dreamers` has a **feedback loop** (status_sync corrects it), and `lanes` does not. That is
the structural reason one tracks reality and the other froze: not a miscount, not a cache — a
field with no correction mechanism drifts indefinitely in whichever direction the last human
edit left it.

## There are two sources, not three

The brief asked "why are there three?" The answer: **there aren't.** `recorded` and `runners`
both call `len(lanes)` / iterate `lanes` — they are one source presented as two dot-separated
fleet counts. A coordinator reading `lanes 3 recorded · runners ccc 3 · 5 ccc-live` sees three
numbers and must adjudicate; in reality the first two are locked together by construction (same
list), and the disagreement is purely recorded-vs-observed.

## The upper-bound claim is falsified

The pre-#718 `_fleet_fact` docstring claimed `recorded` "sees every dispatch form, so it
cannot be deflated by the probe's blindness; it goes stale upward ... an upper bound." The
measurement falsifies every clause:
- "Sees every dispatch form" — it saw none of the five dispatches tonight (stuck at 3).
- "Goes stale upward" — it went stale **downward** (3 against 5 running).
- "An upper bound" — a hand-maintained field with no automatic writer is not bounded in either
  direction; it is an untethered snapshot.

A coordinator who believes `recorded` is an upper bound and sees `3 recorded · 5 ccc-live`
will conclude the observation (5) is wrong, because nothing can exceed an upper bound. That is
the trap the brief named: "I nearly acted on it."

## The fix (all in `tick_line.py`)

**Decision: recorded-vs-observed is a real distinction, so the labels are the defect** (the
brief's second option, argued not picked). Three changes, all in `_fleet_fact` + docstring:

1. **Stop presenting one source as two counts.** Fold the runner breakdown into the `recorded`
   fragment as a parenthetical, so the line reads as TWO fleet figures (one per source) not
   three. `lanes 3 recorded · runners ccc 3 · 5 ccc-live` becomes
   `lanes 3 recorded (ccc 3) · 5 ccc-live`. A parenthetical is a qualification of what
   precedes it, not an independent assertion — so a stale `3` in both positions reads as one
   claim, not as corroboration.

2. **Retract the upper-bound claim** in the docstring. State what `recorded` actually is: a
   hand-maintained record with no automatic correction, which drifts in whichever direction the
   last edit left it.

3. **Keep the runner breakdown** — it is the policy mirror #673 explicitly asked for ("reached
   for native by habit"), and it is compaction-safe (the dashboard is not). Dropping it would
   remove a working signal to fix a labelling problem.

`runners` as a standalone fleet count goes; its information (which models, in what ratio)
stays as a parenthetical of `recorded`.

## Red-proof

### Direction 1 — the parenthetical format (injected, went RED, restored, check clean)

**Injection:** reverted `_fleet_fact` to present the runner breakdown as a dot-separated
clause (`recorded += SEP + "runners " + breakdown`) instead of the parenthetical.

**Discriminating failure message:**

```
AssertionError: assert 'lanes 3 recorded (ccc 3)' in 'lanes 3 recorded · runners ccc 3 · 5 ccc-live · ...'
```

The test asserts the parenthetical form; the injected code produces the old
`· runners ccc 3` form. A fixed-fixture test asserting the old format would PASS against this
injection — it can only be caught by a test asserting the NEW format.

**Frozen-counter differential** (`test_recorded_count_is_reread_each_call_not_frozen`):
rewrites `lanes` from 2 entries to 5 under an already-read target and requires the count to
move. This passes against current code (no cache in `tick_line.py`). The injection that would
freeze it — a per-target `lru_cache` on `_read_status` — would make the second read still say
`lanes 2 recorded`, failing on `assert "lanes 5 recorded" in after`. Mirrors the existing
posture-half guard (`test_posture_is_reread_within_one_target_not_cached`).

**`dev/redproof.py check` (post-rebase):**

```
history: examined 4 commit(s) since 255d6427e564 (master) against 1 injected path(s); read 4 blob(s), 0 holding a recorded injection.
check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits:
  tick_line.py (sha 563424fc2c4a, hint: 'recorded += SEP + "runners " + breakdown')
```

### Direction 2 — all three agree and the line still misleads (OPEN, not closeable)

Constructed: `lanes` holds 3, `dreamers` has 3 live pids, reality is 3. The line reads
`lanes 3 recorded (ccc 3) · 3 ccc-live` — everything agrees. But `lanes` is still
hand-maintained with no correction mechanism. The coordinator, trained by tonight's agreement
to trust `recorded`, dispatches a 4th lane and forgets to update `lanes`. Next tick:
`3 recorded (ccc 3) · 4 ccc-live`. The coordinator who internalised the old upper-bound claim
thinks the 4 is wrong.

**Not closeable by any test:** the line IS correct at the moment of agreement — the defect is
in the FUTURE staleness, which no point-in-time test can see. The mitigation is the docstring
retraction (so the coordinator knows `recorded` is hand-maintained, not an upper bound, and
trusts `ccc-live` when they diverge), not a test guard. A test pinning "the docstring does not
claim upper bound" would be a string-match on prose, which `#699` measured as unreliable.

**The sampling case is acceptable; the `recorded` case is not.** `ccc-live` taken microseconds
before a dispatch is correct-but-stale. What makes it acceptable: its error is **bounded** (the
next tick, 4.5 minutes later, self-corrects it) and **honest** (it is labelled observation, and
observation is inherently point-in-time). `recorded`'s staleness is **unbounded** (no automatic
correction — only a manual edit) and was **dishonest** (labelled an upper bound when it isn't —
now retracted). So sampling is acceptable for the OS probe because its error is bounded and
self-correcting; the recorded counter's error is neither.

## Cited issues, relied-on lines

- **#673** (the tick line itself): *"A line reading `delegation 5 · 0 lanes live` under those
  conditions is not a small inaccuracy. It is the precise inverse of the signal #673 asks
  for."* The fleet figures are the point, not decoration — so a frozen fleet figure is not a
  small defect.

- **#513** (the steer this extends): *"restate the posture at each tick, don't just re-read
  it."* The tick exists to surface drift; a frozen counter beside a live one produces drift the
  other way, and just as blindly.

- **#136** (*"one lane is live" and "I cannot see the fleet" must not render identically*):
  the relied-on principle — two different states must not look the same. `3 recorded` beside
  `5 ccc-live` looks like "the bookkeeping says 3, the OS says 5" (a useful signal) when
  actually it is "the bookkeeping is stale, the OS is right" (the alarm). The labels must
  distinguish.

- **#671** (*"a counter that examined nothing must not read as a count"*): `recorded` examined
  a field nobody maintained — it read 3 confidently across five dispatches. A counter reading a
  stale source must not present as a live upper bound.

- **#612** (volume): three dot-separated fleet counts where two share a source is volume that
  actively misleads. Two figures (one per source) is the minimum honest set.

## Out of scope (named, not fixed)

- **`lanes` has no automatic writer.** The fix relabels its output; it does not make the field
  get maintained. Making `status_sync` own `lanes` (append at dispatch, prune at merge) would
  fix the staleness at the source — but `status_sync.py` is #716's file and is not touched.
  This is the deeper fix and it is blocked on #716.

- **`dreamers` is also hand-appended** (the dispatch tooling writes neither field). It stays
  honest only because `status_sync` prunes it. If `status_sync` stops running, `ccc-live`
  drifts too. Not a defect today, but the asymmetry (dreamers pruned, lanes not) is the whole
  story.

## Rebase

Master moved from `62a9ce22` to `255d6427` (5 commits: #716, #715, #717 merges + #720). None
touched `tick_line.py`, `test_tick_line.py`, or `SKILL.md`. Rebase was clean — no conflicts.
Post-rebase: 44 passed in `test_tick_line.py`, redproof check clean.

## Dogfood report

- The brief's framing ("three disagreeing counters") was slightly wrong — there are two
  sources, and two of the three counters are the same source presented twice. This made the
  task look bigger than it was until I traced `_fleet_fact` and saw both `recorded` and
  `runners` call into the same `lanes` list. Not a complaint — the brief's narrowing ("keep
  ccc-live, find what feeds the two frozen numbers") was exactly right and saved the diagnosis.

- The `dev/ledger.py get` refusal-from-worktree gate worked exactly as documented — one wasted
  call, then the brief's invocation form worked. Good friction.

- `just pytest -q <file>` does not work (the recipe takes no args); `python3 -m pytest <file>
  -q` does. The brief says "Name the files you ran" but the just recipe form isn't the one that
  takes file args. Minor.
