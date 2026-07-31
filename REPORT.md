# Lane report — `#720`: resolve() the target so discovery works under the default invocation

**Verdict: DONE.** Both halves landed in one commit (`64b9da38`, rebased onto `13e8b8c6`).
The discriminating test — start from `dreamers: []`, assert repopulation — is in place
and red-proved both directions. `dev/redproof.py check` is clean.

## What I changed and why

### 1. The path fix (`status_sync.py:339`)

```python
# before (the bug):
wt_root = str(target) + "/" + WORKTREE_DIR
# after (the fix):
wt_root = str(target.resolve()) + "/" + WORKTREE_DIR
```

`str(target)` with `--target="."` (the default, what `just status-sync` passes) produced
`"./.worktrees"`, tested with `startswith` against the **absolute** path `readlink` returns.
It never matched. `resolve()` normalises the relative path — and the symlink — to the real
absolute path the lane cwds share.

**Why `resolve()` and not `abspath` or `realpath`:**

- **Not `realpath`**: #425's symlink contract records that `realpath` moves `dirname` into
  `deprecated/`. Verified the repo IS reached through a symlink
  (`~/.claude-p/skills/ud-dreamwork → ~/.llm-general/skills/ud-dreamwork`).
- **`resolve()` over `abspath`**: this is the direction-2 case (see below). Measured: when
  the loop is invoked through the symlink path (`~/.claude-p/skills/ud-dreamwork`), lane
  cwds carry the **real** path (`~/.llm-general/skills/ud-dreamwork`) because the kernel
  resolves cwd symlinks. `abspath` keeps the symlink; `resolve()` normalises to the real
  path. `abspath` would fail under the symlink invocation — the same bug in a different hat.
  All three agree for the default `.` case; `resolve()` is strictly more correct.

### 2. Model derivation (`status_sync.py:_ccc_model`, new helper)

A discovered lane had `model: None` while a hand-written one carried `ccc @glm52` /
`ccc cc +high (opus)` — the same kind of lane rendering as two kinds. The model IS
recoverable from the same `/proc` read discovery already does. Added `_ccc_model(pid)`
which reads `/proc/<pid>/cmdline`, splits on NUL, and inspects `argv[1:3]`:

- `cc` in `argv[1:3]` → `"ccc cc +high (opus)"` (the Opus form: `ccc cc -y +high`)
- an element starting `@` → `"ccc @<alias>"` (the cheap form: `ccc -y @glm52`)
- otherwise → `None`

**The trap, avoided:** reads argv **elements** (NUL-split), never a substring of the raw
cmdline. `/proc/<pid>/cmdline` is NUL-separated, so `b" cc " in raw` never matches and every
lane silently reads as the default model — the exact trap #716 recorded and I fell into
hand-writing this field. `_is_ccc_proc` already does it right (splits on `b"\x00"`); `_ccc_model`
follows it.

**The #702 question — reported or left None?** Left `None`, and here is the one sentence:
#719's phantom is a lane the probe **cannot classify** (the worktree is gone — is it exiting
or hung?), so #702's "must report" reaches it; an unrecognised model alias is an **attribute**
of a lane the probe HAS already classified (it is a live `ccc` lane under `.worktrees/`), so
#702 does not reach it. Reporting it would conflate "I cannot tell what this is" with "I know
what this is but not its model" — the #136 shape.

### 3. The `discover_lanes` return became a 3-tuple

`found` entries are now `(lane, pid, model)` (was `(lane, pid)`). `main`'s merge loop
unpacks the model and sets `entry["model"]` only when it is not `None`. `phantoms` stays
a 2-tuple (no model to derive for a process whose worktree is gone). One existing test
assertion updated to match.

## The test — the half you care about

**`TestDiscoveryRepopulatesFromEmpty`** (`test_status_sync.py:1352`): the discriminating
test. It starts from `dreamers: []`, spawns a real ccc-shaped process in a real
`.worktrees/<lane>` dir, and invokes `main(["--target", "."])` — the production shape —
then asserts the field **repopulates**:

```python
assert len(result["dreamers"]) == 1, \
    "dreamers must repopulate from [] under the default relative target; got %s" \
    % result["dreamers"]
```

A test against a pre-populated fixture passes against the inert implementation — that is
why the bug merged. This test cannot: under the bug, `wt_root="./.worktrees"` never matched
the absolute lane cwd, discovery returned `[]`, and `dreamers` stayed `[]`.

Three tests in the class:
1. `test_repopulates_from_empty_under_default_relative_target` — the core assertion.
2. `test_check_exits_one_when_repopulatable_from_empty` — `--check` must exit 1 (stale)
   without writing when a lane is discoverable but the field is empty. Under the bug,
   discovery found nothing and `--check` exited 0 ("already in sync") over a field that
   should carry a live lane.
3. `test_resolve_not_abspath_through_symlink` — direction 2 (below).

**`TestDiscoveryDerivesModel`** (`test_status_sync.py:1517`): five tests covering the
model derivation. The NUL-split parsing is tested directly against known cmdline bytes
(a perl proxy cannot place the alias in `argv[1:3]`: perl needs `-e` first, so `argv[1]`
is always `-e`). `test_substring_of_raw_cmdline_never_matches` proves the element
comparison succeeds where the substring test fails — binding the parser to the
NUL-split specifically.

## Red-proof — both directions

### Direction 1: inject the real defect, watch the discriminating failure

**Injection 1 (the path bug):** `dev/redproof.py begin status_sync.py`, then reverted
`target.resolve()` back to `str(target)`. Result:

```
FAILED test_status_sync.py::TestDiscoveryRepopulatesFromEmpty::test_repopulates_from_empty_under_default_relative_target
AssertionError: dreamers must repopulate from [] under the default relative target; got []
assert 0 == 1
```

The `--check` test reds too:
```
FAILED test_status_sync.py::TestDiscoveryRepopulatesFromEmpty::test_check_exits_one_when_repopulatable_from_empty
AssertionError: assert 'discovered' in ''
```

Both red on the **discriminating message** (repopulate-from-empty / discovery report
absent), not on a count. A count-only check against a pre-populated fixture would have
passed.

**Injection 2 (the model trap):** reverted `_ccc_model` to the substring test
(`b" cc " in raw`). Result:

```
FAILED test_status_sync.py::TestDiscoveryDerivesModel::test_opus_form_derived_from_nul_separated_argv
AssertionError: opus form must read as 'ccc cc +high (opus)': None
```

The substring never matches the NUL-separated cmdline, so the opus form reads as `None`.

Both restored; `dev/redproof.py check` quoted below.

### Direction 2: construct a case where the path resolves but discovery still lies

**Named and closed:** the symlink case. The brief predicted: "a target reached via a
**different symlink** than the one the lanes' cwd reports — both paths are correct and do
not string-match." This repo IS that case: `~/.claude-p/skills/ud-dreamwork` (symlink) vs
`~/.llm-general/skills/ud-dreamwork` (real, what lane cwds carry).

Measured: `abspath` keeps the symlink path; `resolve()` normalises to the real path.
A loop invoked through the symlink with `abspath` would build `wt_root` under the symlink
path and match nothing — the same bug. `test_resolve_not_abpath_through_symlink` builds a
real symlink, spawns a lane whose cwd is the real path, and discovers through the link;
`resolve()` normalises and the lane is found.

**Why this was the real direction-2 candidate and not the others:** a relative target with
`..` resolves identically under `resolve()` and `abspath` (both collapse it), so it cannot
distinguish them. A worktree root that is itself a symlink does not apply — `wt_root` is
built by string concat, not read from disk, so its symlink-ness never enters the comparison.

## `dev/redproof.py check` — quoted

```
check: clean — 2 injection(s) registered, all restored and absent from the working tree and from this branch's commits:
  status_sync.py (sha 94de79c08d19, hint: 'wt_root = str(target) + "/" + WORKTREE_DIR')
  status_sync.py (sha 35192647d7b6, hint: 'if b" cc " in raw:                          # SABOTAGE: substring trap')
```

Two injections to one file counted as two — matches the `#717` accounting note.

## Verification

- **`python3 -m pytest test_status_sync.py`**: **42 passed** (was 34 at `#719`; +8 new
  tests across the two new classes).
- **`--check` exits without writing**: verified against the real `.dreamwork/status.json`
  — `rc=0`, file byte-identical before/after. The `#702` safe-on-a-bad-tick contract holds.
- **Live demonstration** (the brief's required evidence, quoted from a file not a harness):

  Starting from `dreamers: []` against the live fleet (5 ccc lanes), `main(['--target', '.'])`:
  ```
  status_sync: discovered 5 live ccc lane(s) the field did not carry (cwd under .worktrees/; merged, not replaced): [('lane-624sweep', 1611477), ('lane-627writer', 1613795), ('lane-720target', 1564253), ('lane-721backfill', 1599021), ('lane-722drain', 1601160)]
  dreamers after: 5
    lane-624sweep model=ccc @glm52
    lane-627writer model=ccc @glm52
    lane-720target model=ccc @glm52
    lane-721backfill model=ccc @glm52
    lane-722drain model=ccc @glm52
  ```
  All five discovered, all carrying the derived model. The original dreamers were restored
  afterwards.

## Rebase outcome

Branched from `b9b668e4`; master moved to `13e8b8c6` (the `#718` merge — the tick_line.py
work I was told not to touch). Rebased cleanly: `git rebase master` → "Successfully rebased
and updated". No conflicts. No conflict markers (`grep` for all four diff3 forms: clean).
New sha: `64b9da38`. The `#718` changes are in `tick_line.py` and docstrings; my changes are
in `status_sync.py` and `test_status_sync.py` — no overlap.

## Cited issues — relied-on lines quoted

- **#716** (the discovery I am repairing): *"dreamers is advertised as a DERIVED field
  (status_sync prints it under coverage: derived alongside queue and current_task_ids),
  but the derivation only ever SUBTRACTED … Nothing adds a lane."* — my fix is the missing
  ADD, now working under the default invocation.
- **#719** (the phantom guard in the same function, landed minutes before): *"discover_lanes
  returns (found, phantoms); a ccc process whose cwd fails os.path.isdir is excluded from
  the fleet AND reported by the caller, never silently dropped."* — my change preserves this
  contract; `phantoms` stays a 2-tuple, the `isdir` guard is untouched.
- **#425** (the symlink contract): *"when we migrate watch.py … symlink `watch.py` in the
  main dir so clients won't break if the files on disk are updated."* — the constraint is
  that symlinked paths must keep working; my choice of `resolve()` over `realpath` honours
  it, and the direction-2 test proves the symlink case is covered.
- **#136** ("no lanes are running" and "I cannot see any lanes" must not render identically):
  this bug WAS that shape — the inert version reported `already in sync` while discovery
  contributed nothing. The discriminating test asserts the difference.
- **#612** (volume): the fix is one line (`str(target)` → `str(target.resolve())`); the
  model helper is 20 lines with a focused docstring. Tests are the bulk of the diff.

## Out of scope (named, not fixed)

- **The `brief` path in discovered entries uses the resolved path**, not `args.target`. I
  changed it to `resolved / WORKTREE_DIR / lane / "BRIEF.md"` so it matches the cwd probe's
  resolved root. If a caller passed a symlink target expecting the brief path to carry the
  symlink form, this would differ — but the brief path is only used by the liveness probe's
  `brief in ps` fallback, which compares against `/proc` argv (also resolved), so the
  resolved form is correct. Naming it in case the coordinator sees a reason to prefer the
  raw target.
- **`tick_line.py` (#718)**: untouched, as instructed.

## Dogfood report

1. **The `ccc --help` command hangs** (it waits on stdin). I killed it after timeout. A
   `--help` that blocks is a trap for any agent that runs it to discover the alias config —
   consider `--help` writing to stdout and exiting, or document that `ccc aliases` is the
   non-hanging form (I could not confirm whether `ccc aliases` exists because I abandoned
   the hanging invocation).
2. **The brief's claim about `realpath` was accurate but slightly underspecified.** It said
   "prefer resolve/abspath over realpath" as if they were interchangeable; they are not for
   the symlink case, and the brief's own direction-2 candidate is the thing that
   distinguishes them. The brief could save a lane one false start by naming `resolve()`
   specifically and saying why `abspath` falls short under a symlink target. (I measured
   before choosing, so this cost minutes not the fix.)
3. **The live demo against the main repo's `status_sync.py` initially showed the bug**
   because the main repo runs the pre-fix code. A lane testing discovery against the live
   fleet needs to import from its own worktree, not the repo root — obvious in retrospect,
   but the brief's "demonstrate it live: `just status-sync`" reads as if the installed code
   is the fixed code. Clarifying that the live demo only proves the fix after merge would
   save a lane a diagnostic detour.
