# Lane report — #634 filesystem measurement substrate

## Result

Extended the one existing lane scratch convention rather than adding a sibling:

- `dev/lane_scratch.py measure` derives this lane's named filesystem-measurement directory under the existing lane-private cache root.
- `dev/lane_scratch.py require-mtime-change PATH -- COMMAND...` runs the experiment's exact positive-control command. It is silent at exit 0, reports `UNSUPPORTED` at exit 1 when the command ran but mtime did not advance, and reports `UNDETERMINED` at exit 2 when it could not judge.
- `briefs/boilerplate.md` now requires kernel filesystem identification plus an exact-mechanism positive control before a negative is believed.
- `.dreamwork/lessons.md` gained the uniquely resolving lesson **“A filesystem path is not evidence of a filesystem capability; require the exact positive control before believing a negative.”**

The location is under the existing `~/.cache/ud-dreamwork/lane-scratch` convention, not inside the worktree. That keeps one supported scratch mechanism, derives lane identity rather than trusting a lane-chosen name, avoids dirtying/reaping the worktree with evidence, and currently lands on persistent btrfs. The path itself makes no capability promise; the positive control does that work.

## Base evidence and rebase

The dispatch literal was deliberately wrong. At start:

```text
$ git merge-base HEAD master
1d21a3be7a3dfa0fb0f05b40e99eb1063f6ce7d4
```

The supplied literal was `1d21a3bef1a2ab24b0a1a2e30bd91b4e6f1c1234`; it does not match. Master moved twice while the lane ran. I rebased twice onto local `master`, resolved the append conflict in `.dreamwork/lessons.md` by keeping both lessons, and ran the required line-anchored four-form marker scan. Immediately before writing this report:

```text
master / merge-base: e1decea8cbab69115010b6dafd849d1d5bcbb245
post-rebase code/docs head: aa8cd25198c94e7fc07b31c42651a4d89d3c5b3b
master..HEAD commits:
741cb69f test(#634): specify filesystem positive-control outcomes
a74e1b20 feat(#634): require filesystem measurement controls
aa8cd251 docs(#634): require substrate positive controls
```

The committed report is the successor to that code/docs head; the coordinator should use the branch head reported by git, not a pre-commit self-reference inside the report.

## Filesystem measurements

All types came from the kernel-facing `stat -f` and `/proc/self/mountinfo` reader `findmnt -T`, not from path spelling. Every repo-relative path named in this report is beneath the measured worktree row.

| Location | Kernel reading | Mount |
|---|---|---|
| session scratch root `/tmp/claude-1000` | `tmpfs`, `f_type=0x1021994` | `/tmp`, source `tmpfs`, `rw,noatime,inode64,huge=advise` |
| this worktree | `btrfs`, `f_type=0x9123683e` | `/home`, source `/dev/nvme0n1p5[/@home]`, `rw,noatime,compress=zstd:3,...` |
| derived measurement directory under the lane-private cache | `btrfs`, `f_type=0x9123683e` | same `/home` btrfs mount |

Dogfooding the shipped helper returned:

```text
measurement_dir=/home/xertrov/.cache/ud-dreamwork/lane-scratch/ud-dreamwork/cx-634fs/measure
type=btrfs f_type=0x9123683e
positive_control_rc=0 stdout_bytes=0 stderr_bytes=0
```

That is one healthy firing in one invocation: zero false warnings, with silence measured rather than inferred.

## Original-defect reproduction: current result contradicts the brief

I could not honestly produce the required “clean NO on tmpfs, YES on real disk” on this current machine. Two controlled probes gave different results from the task premise:

1. A page-sized file had its mtime set 60 seconds old, was mapped `MAP_SHARED`/read-write, one byte was changed, and the mtime was read while the mapping was still live. It advanced **15/15 on tmpfs and 15/15 on btrfs**.
2. A read-only query against a copied ledger fixture, with a second WAL connection held open and a recent fixture-only write, advanced `-shm` mtime **0/15 on tmpfs and 0/15 on btrfs**.

The direct mmap probe is reproducible with this core operation inside a temporary directory on each parent:

```python
p.write_bytes(b"0" * mmap.PAGESIZE)
os.utime(p, ns=(old_ns, old_ns))
before = p.stat().st_mtime_ns
f = p.open("r+b", buffering=0)
mm = mmap.mmap(f.fileno(), mmap.PAGESIZE,
               flags=mmap.MAP_SHARED,
               prot=mmap.PROT_READ | mmap.PROT_WRITE)
mm[0] = 49
after = p.stat().st_mtime_ns
```

The copied-ledger probe is reproducible by copying the live database read-only into a temporary `.dreamwork/`, opening only the copy in WAL mode, making a fixture-only write, holding that connection, then recording `ledger.sqlite3-shm` `st_mtime_ns` around `ledger_parse.store_ids_by_state(fixture_dw)`.

This does not refute the historical live observation; it does refute treating the filesystem label, a generic mmap write, or a quiescent SQLite read as a substitute positive control for the exact live read-mark transition. I did not rewrite the evidence into the requested shape.

## Trap coverage

| Trap | Status | Evidence / limit |
|---|---|---|
| 1 — infer tmpfs from a path prefix | Closed | Neither helper nor boilerplate infers capability from `/tmp`, repo-locality, or any prefix. The boilerplate requires `stat -f` / `findmnt`. |
| 2 — “not tmpfs” implies suitable | Closed for mtime probes | The previous `test_root_is_not_tmpfs` claim was removed as insufficient. Filesystem type is diagnostic only; the gate compares the actual subject before and after the control. |
| 3 — exhibit the phenomenon first | Closed for mtime probes when the supplied command uses the exact mechanism | The command must advance the same subject's mtime before a negative is accepted. The helper cannot prove semantic homology between an arbitrary command and a later probe. Non-mtime phenomena remain open and explicitly require their own positive control. |

Direction 2 of the red-proof deliberately constructed that remaining misuse: a substitute `os.utime` control exited 0 silently, followed by a no-op “real” measurement whose mtime delta was zero. Raw result:

```text
substitute_touch_control_rc=0 control_output_bytes=0
real_noop_measurement_mtime_moved=False delta_ns=0
```

That is why the docs say a touch control does not validate mmap. The mechanical gate closes skipped/non-exhibiting mtime controls; it cannot establish that the author supplied the right phenomenon.

## Verification

- Born-red: before implementation, `just pytest test_lane_scratch.py` produced `4 failed, 18 passed`; all four new outcome tests failed because the CLI did not exist.
- Discriminating injection: `dev/redproof.py` snapshotted the fixed `dev/lane_scratch.py`; changing the `UNSUPPORTED` arm from `return 1` to `return 0` made `test_control_that_exhibits_nothing_is_unsupported_not_ok` fail at `assert 0 == 1`, while stderr still named the non-moving mtime. Restore was byte-verified.
- Red-proof exit gate: `check: clean — 1 injection(s) registered, all restored`; it examined two branch commits and found zero blobs holding the injection.
- Final targeted lane suite after the final rebase: `just pytest test_lane_scratch.py` — **22 passed**.
- Final lint after the final rebase: `python3 lint.py` — **clean, 6 warnings**, exactly the lane bar: answered-question dates; absent worktree ledger; absent status; zero-entry marker check; pre-existing near-duplicate lesson; zero-entry ledger checks.
- No browser guards, ports, full pytest, live-ledger mutation, `attn`, merge, or push were used.

## DOGFOOD REPORT

The new authority-and-contradiction paragraph in `briefs/boilerplate.md` was clear enough to act on. The task head's targeted `just pytest <files>` instruction agreed with the standing contract. Had the head requested the bare suite without naming an override, the paragraph unambiguously says the standing targeted rule wins and the conflict must be reported.

The deliberate bad base literal was also caught cleanly: reading `git merge-base HEAD master` produced verifiable evidence, and rechecking before handoff caught master moving twice. The append-only lesson conflict was straightforward keep-both work in the lane, where the context belonged.

The useful friction was in the task's measurement premise. “tmpfs gives NO, btrfs gives YES” did not reproduce under either a controlled direct mmap write or the hermetic copied-ledger read. The brief did say to measure before building and allowed honest open traps, which made the correct response clear: preserve the contradictory evidence, narrow the helper's promise, and make the exact positive-control command part of the interface. The boilerplate was clear; the historical premise was not current enough to treat as a result.
