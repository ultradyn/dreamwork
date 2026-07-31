# Lane #675 report — live-lane probe blind to Agent-tool dispatch

## RE-MEASUREMENT (the three opening questions)

### 1. What does `live_lanes` match on today, vs `discover_lanes`?

**`live_lanes(dreamers)`** (status_sync.py:152) does NOT probe the process
table directly. It reads `status.json['dreamers']` and matches each entry
by **pid** (`kill -0`, the exact signal) or, as a fallback, by **brief
path** substring against a `pgrep -af ccc` listing. It is a *verification*
function: it checks whether recorded entries are still alive. It cannot
discover lanes that are not already recorded.

**`discover_lanes(target)`** (status_sync.py:335) is the *discovery*
function added by #716/#720. It walks `/proc/*/cwd` for processes whose
cwd is under `<target>/.worktrees/`, then filters by `_is_ccc_proc` (argv[0]
basename == `ccc`). So today there is ONE cwd-walk probe, but it only admits
`ccc` processes — an Agent-tool lane (no `ccc` in argv) is structurally
invisible to the admission filter even though the cwd-walk already reaches
it.

### 2. Which feeds `ccc-live`, which feeds `current_task_ids`?

- **`ccc-live`** (the tick line, tick_line.py `_fleet_fact`) calls
  `live_lanes` on `status.json['dreamers']` entries whose dispatch is
  observable (`ccc`). It counts lanes whose **recorded** process is still
  alive — it can only count what the coordinator recorded or what
  `discover_lanes` merged in on a prior tick.
- **`current_task_ids`** (status_sync.py `main`) is derived from the
  survivors of `live_lanes` PLUS the `discover_lanes` merge PLUS
  unobservable entries carried verbatim. So discovery feeds it, but only
  the ccc half — Agent-tool lanes are absent.

### 3. Is the entry's symptom (`0 live` while lanes run) still reproducible?

**The original symptom is NO LONGER reproducible for ccc lanes.** #720
fixed `discover_lanes` (resolve the target so the cwd prefix matches), and
right now `discover_lanes` against the live target returns 3 live ccc lanes
correctly:

```
FOUND (ccc only): [('lane-606load', 1758402, 'ccc @glm52'),
                   ('lane-608redproof', 1726675, 'ccc @glm52'),
                   ('lane-675probe', 1689176, 'ccc @glm52')]
```

**The residual gap is real and is what the brief predicted:**
`_is_ccc_proc` filters to argv[0]==`ccc`, so an Agent-tool subagent (no
`ccc` in argv) is invisible. The `/proc` scan in my measurement confirmed
this: each live ccc lane has 4–5 sibling processes (zsh wrapper, grok
child, codebase-memory-mcp) sharing the same cwd, all non-ccc, all
invisible to the current probe. The brief's option 4 — "discover_lanes
already walks /proc for cwd-under-.worktrees/" — is the correct seam: a
non-ccc process with a lane cwd is precisely an Agent-tool lane's shape.

## What I changed

1. **`discover_lanes` returns a third list, `agent_tool`** — non-ccc
   processes with a lane cwd, deduped by lane name (so a ccc lane's grok
   child does not double-count). The phantom check (`os.path.isdir`) now
   applies to both arms.

2. **`main()` merges `agent_tool` entries into `dreamers`** with
   `dispatch: "agent_tool"`, so `current_task_ids` counts them and the live
   count does not degrade to 0 while Agent-tool lanes run — the drift alarm
   Max asked the loop to watch for (#673). They are REPORTED on stderr
   separately from ccc, never silently mixed.

3. **`OBSERVABLE_DISPATCH` gains `"agent_tool"`** — an agent_tool entry has
   a pid `kill -0` can reach, so the next tick's `live_lanes` can reap it
   by pid (unlike `spawn_subagent`, which has no probe-able pid and is
   carried verbatim).

## Direction 1 (red-proof): the injection

Sabotaged the `else` arm in `discover_lanes` to `pass` (skip non-ccc
processes — the #675 bug). Two tests went red on the discriminating
messages:

```
test_nonccc_lane_cwd_is_discovered_as_agent_tool:
  assert ('lane-675agent', 1863759) in []   # agent_tool list is empty

test_agent_tool_lane_merged_into_dreamers:
  AssertionError: agent-tool lane must be counted as live (not 0): []
  assert 675 in set()                       # dreamers is empty
```

Restored via `dev/redproof.py restore` — verified, no SABOTAGE remains.

## Direction 2 (false-green): the over-count

**Named, not closed.** A non-ccc process with a lane cwd that is NOT a lane
(an editor opened in the worktree, a shell, a `grep` from inside the
worktree) will be counted as a live lane. This is the over-count cost the
brief and the #675 entry both name, and it is the ACCEPTED trade: an
over-count by one transient process is self-correcting on the next tick
(the process exits and is gone); the ZERO it replaces is the one value that
means "nothing is running" and fires the drift alarm permanently. The
dedup-by-lane-name guard prevents the common case (a ccc lane and its grok
child) from double-counting, but it cannot distinguish a real Agent-tool
lane from an editor in the same worktree. That discrimination would require
a signal this probe does not have (a harness task registry, or a lane
liveness file — both ruled out by the module's "no memory" contract).

## Verification

- `python3 -m pytest test_status_sync.py -q`: **42 → 46 passed**
- `python3 lint.py`: **clean (6 warnings, expected in a worktree — #611)**
- `--check` exits 1 (stale) without writing: verified with a fixture
- `python3 dev/redproof.py check`: **clean** — injection restored and
  absent from the working tree and from this branch's commits

## Rebase

Rebased onto local master (`b0051bf9`), clean, no conflicts. New HEAD:
`a28e67b3`.

## Out of scope (do not fix — name it)

- **tick_line.py's `_fleet_fact`** still labels the OS measurement
  `ccc-live` and its docstring says the probe "sees the ccc dispatch path
  and nothing else." After this change the probe sees agent_tool too, so
  the tick line's `ccc-live` count now includes agent_tool entries (they
  flow through `live_lanes` as observable). The brief says "do not change
  tick_line.py's rendering; if your change alters what it should print, say
  so and stop." It does alter the semantics: `ccc-live` is now
  `ccc-plus-agent-tool-live`. The count is more honest (closer to the real
  fleet) but the label is less precise. Filing for the coordinator to
  decide whether to rename the label or keep it.
