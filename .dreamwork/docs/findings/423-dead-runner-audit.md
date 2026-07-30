# #423 — dead-runner signal — audit under the CURRENT dispatch paths

**Lane:** `lane-423runner` (read-only audit). **Task body:** `#423` — `ccc @grok`
401s recur, and the loop has no signal for a dead runner. The filing asks for a
dispatch-time runner probe and a lane-failed recording. **But the dispatch
topology changed** (DREAMWORK.md:364–370): this session dispatches via the Grok
harness's native `spawn_subagent`, and the `ccc`-runner bullets are explicitly
"the previous harness's form of the same two-model policy." So this audit asks:
what is live, what is moot, what is the minimal true fix.

Every claim below cites a file:line verified in this worktree while writing.
Inherited claims (from `dogfood-orchestration.md`, `questions.md`, the task
body) were re-verified against current code.

---

## Headline verdict

**Partially moot, one live gap remains, and it is NOT the gap the task was
filed against.** The two mechanisms the task body asked for map onto the two
dispatch paths as follows:

| mechanism the task asked for | under `spawn_subagent` (current) | under `ccc` (previous) |
|---|---|---|
| dispatch-time runner probe (PONG round-trip) | **moot** — the harness reports completion/failure itself; a dead model is a failed spawn, not an exit-0 no-op | **moot** — the `ccc` path is disused (DREAMWORK.md:364–370; no live `ccc` process, no wrapper in the repo) |
| lane-exited-without-committing → recorded FAILED | **STILL LIVE** — and the existing lane-containment machinery does NOT cover it, because `spawn_subagent` isolation is an **independent clone**, not a git linked worktree | the gap as filed; the path is disused |

The 401-exits-0 defect (the *runner* signal) is moot on both paths. The
3rd-instance defect (the *lane-work* signal — "is the worktree dirty at exit")
is **live on the current path**, and the task body's own words name the right
check for it: *"the missing signal is not 'did the pid die' but 'is the
worktree dirty at exit'"*. The recommended fix is the smallest possible
instance of that check.

---

## Q1 — Under `spawn_subagent` (the current path): can a lane die silently?

**The runner-death half (401-exits-0): NO.** The Grok harness's
`spawn_subagent` returns a completion notification the coordinator receives
in-conversation, and `get_command_or_subagent_output` reports exit state. A
401/credential failure is a spawn that fails or a subagent that returns an
error, not a process that exits 0 in the background while the coordinator
believes it is working. This is a categorical difference from `nohup ccc … &`,
which detached the dispatch and exited 0 regardless of the child's fate.

**The lane-work half (exited without committing): YES, and this is the live
gap.** The #404 property — *"a lane cannot land work without committing"*
(SKILL.md:92, `dev/ledger.py:230–232`) — is the loop's primary landing signal,
and `dev/ledger.py sweep` (`dev/ledger.py:254`, invoked `dev/ledger.py:476`
`git log --format=%h<ssep>%s`) discovers committed landings from git subjects.
But that property is **a statement about committed work**, and it is structurally
blind to the case the task body's 3rd instance documents: a lane that **worked
but did not commit**. Three facts make that case reachable and invisible today:

1. **`sweep` reads commit subjects only** (`dev/ledger.py:476`:
   `git log --format=%h…%s`). An uncommitted edit produces no subject, so the
   sweep that "found nothing" is indistinguishable from one whose lane did
   nothing — exactly the indistinguishability the task body describes.

2. **The existing lane-containment machinery does not cover `spawn_subagent`
   lanes.** `dev/lane_guard.py`'s lane registry is `git worktree list
   --porcelain` filtered to `wt/*` branches
   (`dev/lane_guard.py:147–148`, `:80` `LANE_BRANCH_PREFIX = "wt/"`), and
   lint's `_live_lane_worktrees` (referenced at `dev/lane_guard.py:589`) reads
   the same registry. **A `spawn_subagent` lane is NOT a git linked worktree**:
   this lane's own `.git` is a full independent directory
   (`git rev-parse --absolute-git-dir` →
   `…/subagent-019fb07a-….git`; no `.git/commondir`; `git worktree list` lists
   only itself on `master`, not under `wt/`). So the pre-commit guard
   (`dev/lane_guard.py:check`, `:271`), the pre-merge assertion
   (`dev/lane_guard.py:_pre_merge`, `:565`), and lint's dirty-path backstop
   (`lint.py:3496`, `:3544`) **all enumerate zero lanes for a harness-clone
   dispatch** — they were built for the `git worktree`-based `ccc` topology and
   see nothing under `spawn_subagent`.

3. **The coordinator's completion handling is manual judgement, not a
   dirtiness check.** When a lane completes, the coordinator does serial ledger
   edits and reads claims (`dogfood-orchestration.md:476–480`: *"Every lane
   that finishes generates work only the coordinator may do"*) — but nothing
   automated runs `git status --porcelain` on the lane's tree at exit. The
   completion notice arriving is the coordinator's cue to act, and if the
   coordinator does not check (or the notice is lost to compaction —
   `lessons.md:3228`: *"Compaction loses the subagent HANDLES… treat a lost
   handle as UNKNOWN, not dead"*), a dirty tree sits recoverable-but-invisible
   until a routine `git worktree remove` would destroy it — the exact loss the
   task body records for `gate2` (`da197b87`, "lane work, committed by the
   coordinator").

**Residual blind spot, named precisely:** a `spawn_subagent` lane that exits
with a dirty worktree (uncommitted/unstaged edits) AND whose completion notice
is missed (compaction, or a coordinator that trusts "no commit ⇒ no work") is
invisible to every automated signal the loop has. `sweep` sees no commit; the
lane-containment guard sees no `wt/` worktree; `status_sync`'s liveness
(`status_sync.py:149` `live_lanes`) is pid-based and only knows "alive or
gone", not "gone with work left behind". The task body's 3rd instance is this
case, and it cost a hand-recovery (`da197b87`).

---

## Q2 — Under `ccc` (the documented legacy path): is the 401-exits-0 mode still reachable?

**The path is disused, so the mode is moot in practice — but the code that
detected it is still present and would work if the path were revived.**

- **Disused.** DREAMWORK.md:364–370 sets the current dispatch policy:
  *"MODELS, set 2026-07-29 18:02 (this harness's native `spawn_subagent`)"*,
  and the `ccc`-runner bullets are *"the previous harness's form of the same
  two-model policy."* `containment-deficiency.md:44` records native subagents
  (Claude Code / grok native) as *"superseded — not dispatched since
  2026-07-28 23:14"*, and the two `ccc` runners (`@grok`/`@glm52`) are the
  prior harness's mechanism. A live `pgrep -af "ccc @"` at audit time returned
  zero `ccc` dispatch processes (the only match was this lane's own grep
  shadow). The main checkout's `status.json` still carries 4 stale `dreamers`
  entries from 2026-07-29 ccc dispatches — but they predate the cutover and
  carry no `pid`, so `status_sync.py`'s `_pid_alive` (`status_sync.py:124`)
  cannot evaluate them.

- **No dispatch wrapper exists in the repo.** There is no `nohup ccc` script,
  no `subprocess.Popen("ccc …")`, no `ccc` invocation in the justfile. The
  `ccc --yolo @glm52 …/brief.md` form appears **only in `status_sync.py`'s
  comments** (`status_sync.py:106`, `:108`, `:123`) describing what it
  detects. Dispatch via `ccc` was a **manual coordinator action** (`nohup ccc
  @grok … &` typed by the coordinator), which is precisely why the 401-exits-0
  failure was possible: the `nohup` detached the process and the coordinator's
  shell returned 0 regardless of the child's auth failure
  (`dogfood-orchestration.md:1302–1305`).

- **The detection code is intact and correct.** `status_sync.py`'s liveness
  (`#402a`) is pid-primary `kill -0` with a brief-path fallback
  (`status_sync.py:124` `_pid_alive`, `:149` `live_lanes`). Its docstring
  (`status_sync.py:120–133`) records the measured finding that a live
  `ccc --yolo @glm52` process keeps its pid AND argv for the lane's whole
  life, so `kill -0` on the dispatch pid is the exact signal. **This detects
  "is the pid alive" — it does not, and was never meant to, detect "did the
  lane do anything,"** which the task body's 3rd instance explicitly calls out
  as the different missing signal.

- **Nothing today probes a runner before trusting it, or records a
  no-commit/no-inbox exit as FAILED — on either path.** `status_sync.py` only
  prunes `dreamers` whose pid is gone or whose task has landed
  (`status_sync.py:402–408`); it records nothing about *why* a lane left. There
  is no FAILED state for a lane, no dispatch-time PONG probe, and no
  exit-dirtiness recorder anywhere in the repo (verified: grep for
  `worktree.*dirty|at exit|recorded as failed|zero commit` across `*.py`
  returns no production mechanism).

**So the 401-exits-0 mode is technically reachable if `ccc` dispatch is ever
revived, but it is dormant today, and reviving it is the human's dispatch-path
decision (DREAMWORK.md, not loop-owned code). The loop-side half the task was
filed against — a dead runner looking like a fast lane — does not arise under
`spawn_subagent`, because the harness owns completion reporting.**

---

## Q3 — The minimal fix, if any

There is **one** live gap (Q1's lane-work half) worth closing. The runner-probe
half (the task's primary ask) is moot on both paths and should not be built.

### The live gap: a `spawn_subagent` lane that exits dirty is invisible

The task body already names the right check and the right discriminator:
*"the missing signal is not 'did the pid die' but 'is the worktree dirty at
exit' — one `git status --porcelain` per finished lane distinguishes crashed
before working, worked and did not deliver, and delivered, and only the
middle one is recoverable-but-invisible."*

### The seam, and why it is the only one

The fix is a **coordinator-side habit backed by one command, not a new tool**,
because the three plausible seams in the repo are wrong for it:

- **`status_sync.py`** is pid-liveness, not work-liveness (`status_sync.py:149`
  `live_lanes` measures "alive or gone"). Adding a dirtiness probe here would
  conflate two signals and run on every tick (wrong frequency — the check
  belongs at lane *exit*, not every tick). It would also touch the `dreamers`
  shape, which is ccc-path plumbing that `spawn_subagent` does not populate.
- **`dev/lane_guard.py`** and **`lint.py`**'s lane registry is `git worktree
  list --porcelain` filtered to `wt/*` (`dev/lane_guard.py:147`, `:80`), which
  sees zero `spawn_subagent` lanes (they are independent clones, not linked
  worktrees — see Q1). Extending the registry to enumerate harness clones would
  be a larger change than the gap warrants, and lane-containment's purpose is
  preventing main-checkout edits, not recording exit dirtiness.
- **`dev/ledger.py sweep`** reads commit subjects (`dev/ledger.py:476`) and is
  structurally blind to uncommitted work by design; widening it would change
  its contract.

The right home is the **coordinator's lane-completion step**: when a
`spawn_subagent` lane's completion notice arrives (or is reconciled after
compaction), run `git -C <lane-tree> status --porcelain` (and
`git -C <lane-tree> log --oneline -1`) before treating the lane as done. The
three cases the task body names fall out directly:

| exit state | `git log` since dispatch | `git status --porcelain` | action |
|---|---|---|---|
| delivered | non-empty (new commits) | clean | fold normally |
| crashed before working | empty | clean | no work lost; retire quietly |
| **worked, did not deliver** | empty | **dirty** | **recoverable-but-invisible → commit on the lane's behalf or salvage, and record** |

This is one command at one step, reuses the existing `--porcelain` idiom
(`dev/lane_guard.py:516`, `lint.py:3544`), and closes exactly the
`gate2`/`da197b87` loss. **It is a dispatch-prompt / SKILL.md-habit fix, not a
production-code change** — the coordinator owns lane completion, and the check
is a one-line `git status` the coordinator runs, not a tool the repo ships.

### Why no IGC is needed

There are not rival *mechanisms* competing for the same seam — there is one
live gap, and the three repo-side candidates are each refuted for a decisive
reason (wrong signal, wrong registry, wrong contract). The remaining option
(coordinator-side `git status` at completion) is non-refuted on every goal:
closes the gap, costs one command, touches no production code, reuses an
existing idiom, and fails safe (a dirty tree the coordinator misses is no worse
than today; a clean tree costs one git call). An IGC matrix over a single
survivor is waste per the method's own scale rule (SKILL.md:778,
igc-method.md:50).

### What is NOT being proposed (and why)

- **No dispatch-time PONG probe.** Moot under `spawn_subagent` (the harness
  reports spawn failure) and moot under `ccc` (the path is disused; reviving
  it is the human's decision).
- **No FAILED state in the ledger.** A dirty-exit lane is a coordinator
  recovery, not a task state — the work is recoverable, and "record as failed"
  would add a state machine for a case that is one `git status` away from
  resolution. The task body's "recorded as failed" was filed against the
  `ccc`-exits-0 case, which is moot.
- **No widening of `status_sync`/`lane_guard`/`sweep`.** Each is refuted above.

---

## Q4 — Mootness verdict

**The task as filed is largely moot; one narrower gap survives.**

**Moot, with evidence:**

1. **The 401-exits-0 runner signal** (the task's primary subject) is moot on
   the current path. `spawn_subagent` reports completion/failure itself — a
   dead/401 model is a failed spawn, not an exit-0 background process. The
   `nohup ccc … &` topology that made exit-0-on-401 possible
   (`dogfood-orchestration.md:1302–1305`) is the *previous* harness's dispatch
   form (DREAMWORK.md:364–370), disused since the 2026-07-29 18:02 cutover to
   `spawn_subagent`, with zero live `ccc` processes at audit time and no
   dispatch wrapper in the repo. The loop-side defect — "a dead runner looks
   exactly like a fast lane" — does not arise when the harness owns completion
   reporting.

2. **The dispatch-time PONG probe** is moot for the same reason on the current
   path, and moot on the `ccc` path by disuse.

3. **The "record a no-commit/no-inbox exit as FAILED" ask**, as a *ledger
   state*, is moot — the case it was filed against (ccc-exits-0) does not
   arise, and a dirty-exit recovery is a coordinator action, not a task state.

**Live, with a minimal fix (Q3):** the lane-work half of the 3rd instance — a
`spawn_subagent` lane that exits with a dirty worktree is invisible to
`sweep` (commit-subjects only, `dev/ledger.py:476`), to the lane-containment
guard (registry is `wt/*` linked worktrees, `dev/lane_guard.py:147`, which
harness clones are not), and to `status_sync` (pid-liveness only,
`status_sync.py:149`). The task body names the fix: `git status --porcelain`
at lane completion. **This is a SKILL.md / coordinator-habit change (one
command at the completion step), not production code**, and the brief's
read-only rule is honored — no file is named for a code fix, because the
minimal true fix is not a code change.

**Recommendation:** fold #423 as **moot-with-evidence on the runner-signal
half**, and file the surviving lane-work half (coordinator-side
exit-dirtiness check at lane completion) as a small SKILL.md-habit task or a
one-line addition to the Subagents section's lane-completion guidance. Do
**not** build a runner probe or a FAILED state — the path that needed them is
gone, and the current path's gap is closed by a `git status` the coordinator
already has access to.

---

## Evidence index (file:line, all verified in-worktree)

- Dispatch topology cutover: `DREAMWORK.md:364–370` (spawn_subagent, current);
  `DREAMWORK.md:308–351` (ccc runners, previous harness).
- 401-exits-0 defect as filed: `dogfood-orchestration.md:1300–1306`;
  `questions.md:846–849`; task body (#423 in store).
- #404 landing signal / "cannot land work without committing":
  `SKILL.md:92`; `dev/ledger.py:230–232`, sweep at `dev/ledger.py:254`,
  git subjects at `dev/ledger.py:476`.
- #402a liveness (pid-primary kill -0 + brief fallback):
  `status_sync.py:124` `_pid_alive`, `:149` `live_lanes`, `:402–408` reap.
- Lane-containment registry is `wt/*` linked worktrees:
  `dev/lane_guard.py:80` `LANE_BRANCH_PREFIX`, `:147–148` `_parse_worktree_list`;
  lint's reader at `lint.py:3496`, `:3544`; pre-merge at `dev/lane_guard.py:565`.
- `spawn_subagent` isolation is an independent clone, not a linked worktree:
  this lane's `git rev-parse --absolute-git-dir` → `…/subagent-…/.git` (full
  dir, no `commondir`); `git worktree list` shows only itself on `master`.
- 3rd-instance recovery commit: `da197b87` "docs(#263): … (lane work, committed
  by the coordinator)".
- Coordinator lane-completion is manual judgement:
  `dogfood-orchestration.md:476–480`; compaction-handle loss
  `lessons.md:3228`; `isolation="worktree"` dispatch habit `lessons.md:3240`.
- ccc path disused: no live `ccc @` process; no wrapper in repo
  (`status_sync.py:106/108/123` are detection comments only);
  `containment-deficiency.md:44`.

## Constraints honored

- Read-only except this findings doc. No production code changed; no file
  named for a fix (the minimal fix is a coordinator habit, not code).
  `watch.py` untouched (lane-534sig owns the `_entry_content_digest`/sig-store
  region — `534-sig-store-versioning.md:19` — unrelated to #423).
- No servers, no ports, no `attn`, no `pkill -f`. All git/sqlite queries were
  read-only (`mode=ro` on the store; `git log`/`git status`/`pgrep` only).
- Every claim cites a file:line verified while writing; inherited claims
  re-verified against current code.
