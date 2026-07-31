# Lane 729 report — the phantom list splits self / runner / other

## Verdict: DONE

`status_sync` printed the coordinator's own process and a `head`/`grep`/`tail`
fleet as one bucket labelled *"ccc process mid-exit"* — a specificity the code
never had (it matched any cwd under `.worktrees/`, never read argv; #671). The
fix splits that bucket into three labelled cases, all reported under #702.

## What I changed and why

Two helpers in `status_sync.py`, plus a three-way split in `main`'s phantom
report. The `discover_lanes` 3-tuple contract is untouched — the split is in
the *report*, not the return shape, so `live_lane_count` (`:389`), `main`
(`:712`), and the arity test all still hold.

### `_ancestor_pids()` — ancestry self-exclusion (the primary rule)

Walks `/proc/<pid>/stat` field 4 (ppid) up from `os.getpid()`. Exact, not
heuristic, no allowlist. A process that is an ancestor of the thing doing the
counting is by construction not a lane. Cuts between the FIRST and LAST paren
for comm (which may contain spaces/parens), like `reaper.parse_proc_stat`.

### `_is_lane_runner(pid)` — positive identity (copies `reaper.parse_cmdline`'s shape)

A basename check on NUL-split argv[0] against `(ccc, claude, grok, codex)`,
not a cwd prefix match. This is the #440 exemplar: `reaper.parse_cmdline`
requires a `watch.py` basename **AND** a server flag — that pairing is why the
reaper is safe where it has kill authority. The same shape (a basename check,
not a prefix match) separates a genuine leftover from the shell noise a lane
leaves behind (`head -3`, `grep --line-buffered`, `tail -F`, a handshake
`bash`).

### The split (in `main`, not in `discover_lanes`)

The old single `phantoms` print becomes three, each guarded by `if` so an
empty case prints nothing:

1. **self** — *"the coordinator's own ancestry"* (pid in `_ancestor_pids()`).
2. **leftover** — *"genuine leftover lane runner"* (a known runner with a
   deleted cwd).
3. **other** — *"neither self nor a known runner"* (the #671 shell fragments).

All three fire under #702: an entry the tool cannot classify must be REPORTED,
never silently dropped. #136: self / leftover / unclassifiable are three facts
and need three renderings.

## `just status-sync` against the live tree — before and after

**BEFORE** (single bucket, the #671 false-specific label):

```
status_sync: excluded 5 phantom lane(s) whose worktree is gone (ccc process
mid-exit, cwd no longer a directory; reported not dropped — #719/#702):
[('277-dreamfade (deleted)', 636147), ('askmark (deleted)', 1699640),
 ('askmark (deleted)', 1699643), ('askmark (deleted)', 1699644),
 ('lane-clientextract (deleted)', 1328406)]
```

`pid 1328406` is the coordinator (verified by `/proc` ancestry: my chain is
`2140985 zsh → 2095036 grok → 2095031 ccc → 2095000 zsh → 1328406 claude`).
The other four are `head -3`, `grep`, `tail -F`, a handshake `bash` — not one
is a ccc process. The label claimed a check the code did not perform.

**AFTER** (split into self / other; no runner present on this run):

```
status_sync: 1 phantom entry is the coordinator's own ancestry (deleted cwd
under .worktrees/, but this process is an ancestor of status_sync; not a lane,
reported not dropped — #729/#702): [('lane-clientextract (deleted)', 1328406)]
status_sync: 4 phantom entries are a process with a deleted worktree cwd that
is neither self nor a known runner (e.g. head/grep/tail/bash from a lane's
pipeline; cwd under .worktrees/ matched the old prefix filter — #671/#729;
reported not dropped — #702): [('277-dreamfade (deleted)', 636147),
 ('askmark (deleted)', 1699640), ('askmark (deleted)', 1699643),
 ('askmark (deleted)', 1699644)]
```

The coordinator is labelled **self**; the shell fragments are labelled
**other**; the false-specific "ccc process mid-exit" is gone.

## Red-proof — both directions

### Direction 1 (discriminating): SELF and a genuine leftover are DISTINGUISHABLE

`python3 dev/redproof.py begin status_sync.py` → sabotaged the phantom block
back to the old single bucket → ran `TestPhantomBucketSplit` → **4 failed**,
each on the discriminating message:

- `test_coordinator_ancestor_is_labelled_self_not_phantom` →
  *"an ancestor of status_sync must be labelled self, not a phantom lane"* —
  and the error showed the old single-bucket message with the coordinator's
  pid inside it. This is the brief's Direction 1: the assertion names WHICH
  case, not a count, so it fails against a fix that drops everything.
- `test_shell_fragment_is_labelled_other_not_ccc_midexit` →
  *"the old false-specific label must not appear for a head process (#671)"*
  — pinpoints `"ccc process mid-exit"` appearing over a `head` process.
- `test_ccc_runner_is_labelled_leftover_not_other` →
  *"a ccc runner with deleted cwd must be labelled a genuine leftover"*.
- `test_all_three_cases_reported_none_dropped` →
  *"self case must be reported"* — catches that all three collapse into one.

Committed while sabotaged (`2b81f29`, dropped after restore), then
`python3 dev/redproof.py restore status_sync.py` (sha `2e7b4b15` recorded),
then verified the restored file passes 4/4.

### Direction 2 (the case where the classifier is right but the report misleads)

Constructed: a lane started via a wrapper so `argv[0]` is `bash`
(`bash -c 'ccc -y @glm52 brief'`). Measured: `_is_lane_runner` returns `False`
(argv[0] basename is `bash`, not in `_LANE_RUNNERS`).

**This is a false-negative on runner identity, NOT a false-green.** The
process lands in the **other** bucket and IS reported (under #702), never
silently dropped. The label *"neither self nor a known runner"* is
technically accurate: argv[0] IS `bash`. The mislabel is conservative
(an under-count of runners), not an over-count or a silent drop.

Why I did not fix it: the brief's #440 ask was for a positive test (which I
have — a basename check), not wrapper-recursion. Recursing into a wrapper's
argv to find the hidden runner is a new feature with its own false-positive
risk (a shell that happens to mention `ccc` in a script path). Filed, not
fixed — out of scope.

## `python3 dev/redproof.py check`

```
history: examined 2 commit(s) since 8a00df975dc9 (master) against 1 injected
path(s); read 2 blob(s), 0 holding a recorded injection.
check: clean — 1 injection(s) registered, all restored and absent from the
working tree and from this branch's commits:
  status_sync.py (sha 2e7b4b159845, hint: '# SABOTAGE: reverted to the old
  single bucket (the #729 bug)')
```

The `check` gate initially REFUSED because the sabotage commit `2b81f29` was
still in branch history. I dropped it (`git reset --hard 5fbf9a85` — the
working tree already equalled the pre-sabotage fixed commit, so this moved
only the branch pointer, not any file). Re-ran `check`: clean.

## Verification

- `python3 -m pytest test_status_sync.py -q` → **52 passed** (47 before + 1
  updated + 4 new in `TestPhantomBucketSplit`). Before: 48 passed, 1 failed
  (the existing #719 test that asserted the old `"phantom"` label — updated
  to bind the new "leftover lane runner" arm, since the ccc proxy IS a known
  runner).
- `python3 lint.py` → **clean (6 warning(s))** — no ERRORs. All 6 warnings
  are the pre-existing lane-worktree ones (the gitignored store cannot travel
  from a worktree).
- Non-UI lane — no browser guards run.

## Cited issues, each with its relied-on line

- **#702** — *"an entry the tool cannot classify must be REPORTED, not
  dropped."* This is why I split the bucket rather than shrinking it. Quoted
  from the entry's title-line summary: the govern-the-split rule inherited by
  #719's discovery.
- **#136** — *"THREE zero-states, not one"*; self / leftover / unclassifiable
  are three facts needing three renderings.
- **#671** — *"the label claims a check that was not performed"* — the
  `"ccc process mid-exit"` label over a `grep` / `tail -F` / `head`.
- **#440** — *"one supported way"*; `reaper.parse_cmdline` already IS the
  exemplar (a basename check + a flag), and I copied its shape rather than
  inventing one.
- **#612** — *"Volume"*; the fewest lines that carry the meaning. The change
  is ~60 lines of helpers + ~30 of reporting.

## Rebase outcome

Master moved 3 commits during the work (`236828b5` → `8a00df97`):
`#724`, `#730`, `#724-chore`. `git rebase master` → clean, no conflicts.
Final branch: `5fbf9a85` (test) on `e3e47503` (fix) on `8a00df97` (master).

## The `discover_lanes` 3-tuple contract — NOT changed

I did not change `discover_lanes`'s return shape. The split lives entirely in
`main`'s reporting block, so `live_lane_count` (`:389`) and `main` (`:712`)
still unpack `(found, phantoms, agent_tool)` exactly as before, and
`test_discover_lanes_arity_is_three` still pins the arity. The one caller
outside `status_sync.py` — `dev/guard_preflight.py:135` — calls
`live_lane_count` (the accessor), never a positional unpack, so it is
unaffected by construction.

## Out of scope (named, not fixed)

- **Wrapper-launched runners** (`bash -c 'ccc ...'`) classify as **other**,
  not **leftover** — a false-negative on runner identity, reported not
  dropped. Recursing into a wrapper's argv is a new feature; filed above.
- **pid 741632** (a `watch.py` server from the deleted `frame` worktree,
  3d6h old, port `:40693`) was named in the entry's correction note. It is
  NOT in status_sync's phantom list at all (it is a watch.py *server*, not a
  process with a `.worktrees/` cwd) and is the reaper's domain (#730), not
  this task's. It may still hold a listening port — that is a question for
  the coordinator, not this fixer (#288: selection posture confers no kill
  authority).

## Dogfood report

The brief was excellent — the second-note correction saved me from
re-escalating a P1 that the reaper's construction already defuses, and the
"Direction 1's discriminating assertion" sentence is the one that made me
write tests that name the case rather than the count. Two small frictions:

1. **`dev/redproof.py check` refused on the sabotage commit** even though I
   restored the working tree. The tool is correct to refuse (a merge makes
   the defect reachable forever), and the message names the fix (squash or
   rebase out). But a lane that doesn't read the message carefully might
   hand back a branch the coordinator then has to squash. The
   `git reset --hard <pre-sabotage>` recovery was clean here only because
   the sabotage commit was the tip and the tree was already restored — a
   lane that sabotaged, then made *more* real commits on top, would need a
   `git rebase -i` to drop the middle commit. Worth a one-line note in the
   brief's red-proof section: "to drop a sabotage commit that is the branch
   tip, `git reset --hard HEAD~1` after `restore` (the tree is already
   fixed)."

2. **The existing #719 test asserted the label it was replacing.**
   `test_phantom_not_in_dreamers_report_names_it` asserted `"phantom" in
   err.lower()`, and my split moved the ccc-proxy case out of any
   "phantom"-worded bucket into "leftover lane runner". The test failed for
   the *right* reason (the classification improved), but a lane that didn't
   read the assertion context might have "fixed" it by weakening the label
   back. Not a brief problem — a test-hygiene observation: when a label
   changes, the test that pins it should name the new label in a comment so
   the next reader knows the assertion moved with the contract.
