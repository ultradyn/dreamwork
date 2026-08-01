# Independent session review — `1ab60a3c..8a00df97`

Verdict: **two high-severity regressions, three medium-severity correctness gaps, and three low-severity contract/robustness gaps.** The highest-risk runtime issue is not the Python delta arithmetic: it is the browser accepting an envelope without proving that the response belongs to the base it is about to mutate. Separately, #726's prefix fix removed accidental path confinement and now permits redproof to read and restore files outside the worktree.

Known issues #734 and #732 were excluded as requested.

## Findings

### HIGH — #726 allows a "repo-relative" redproof path to escape the worktree

**Files:** `dev/redproof.py:144-148`, `dev/redproof.py:413-415`, `dev/redproof.py:518-521`, `dev/redproof.py:674`

`_to_posix()` correctly stopped treating `lstrip("./")` as a prefix operation, but `removeprefix("./")` now preserves both absolute paths and leading `../`. `begin()` and `restore()` then join that unchecked string to the worktree root. `pathlib` discards the root for an absolute right operand, and preserves `..` for a relative one. That contradicts the CLI's explicit `repo-relative path` contract and lets the restore step overwrite a file outside the worktree with the saved bytes.

Concrete failing inputs, evaluated against a notional `/worktree/root`:

```text
../victim.txt   => ../victim.txt   => /worktree/root/../victim.txt
/tmp/victim.txt => /tmp/victim.txt => /tmp/victim.txt
```

The dangerous workflow is literal: `begin ../sibling/file`, edit/sabotage that sibling file, then `restore ../sibling/file`; line 520 copies the snapshot back outside the repo. Reject absolute paths and any normalized path containing `..`, or resolve the candidate and require it to remain beneath the resolved worktree root. Add both-direction traversal tests alongside the dotted-path tests.

### HIGH — #641 blindly applies stale or corrupt delta envelopes and can regress an already-newer document

**Files:** `client/router.js:2440-2463`, `client/router.js:4367-4382`; contract at `file-formats.md:2166-2189`

`applyDataResponse()` reads neither `j.base` nor `j.check`. It applies `removed`/`changed` to whatever global `data` happens to hold, then advances global `lastDataV`. This disagrees with the documented "any mismatch, any doubt -> full" and self-heal contracts.

There is also no request sequencing or in-flight guard around `tick()`. Besides the scheduled loop, existing successful write paths call `tick()` directly. Two ticks can therefore overlap:

1. request A starts from v0 and will return delta v0->v1;
2. request B observes v2, returns first, and installs v2;
3. A returns late; `applyDataResponse()` ignores `base=v0`, mutates v2 with the v0->v1 patch, and sets `lastDataV=v1`;
4. global `lastMtime` is already v2, so ordinary polling sees no change and does not repair the regressed/hybrid document until another target write.

Direct concrete input reproducing the bad transition:

```js
data = {x: 2, y: "new"}; lastDataV = "2"; lastMtime = "2";
applyDataResponse({v:"1", base:"0", changed:{x:1}, removed:["y"], check:"bogus"});
// returns {x:1}; lastDataV becomes "1" despite base mismatch and bogus check
```

Capture the requested base per fetch, reject a delta whose `base` is not that base/current held version, sequence responses so older requests cannot commit, and implement the promised canonical SHA-256 check before advancing the version. Any failure must clear `lastDataV` and refetch without `since`. This is distinct from known #732: the defect is wrong acceptance behavior inside the JS implementation, not merely that two implementations exist.

### MEDIUM — #641's cache can serve a stale full document indefinitely when content changes without `watched_mtime` changing

**Files:** `watch.py:3984-3996 @ dc739001`, `watch.py:3999-4006 @ 4e83d224`; contract at `file-formats.md:2172-2178`

`_data_json_cached()` is now authoritative even when the caller sends no `since`; it never calls `collect()` again while `watched_mtime` is equal. This changes the old no-`since` semantics and makes a missed version signal survive page reloads.

Concrete reproduction using the real test fixture:

1. build/cache a target;
2. append `SAME-MTIME-MUTATION` to `.dreamwork/questions.md`;
3. restore that file's exact original `st_mtime_ns` with `os.utime`;
4. call `_data_json_cached(target, None)` again.

Observed:

```text
version_equal_at_lookup True
cache_reused True
cached_has_mutation False
fresh_has_mutation True
```

Two ordinary writes between polls are safe when the final `watched_mtime` advances: the next build compares old state directly with final state. The failing class is two writes within the same observable version, a timestamp-preserving copy/restore, or any other content mutation the current version function aliases. At minimum, no-`since` requests should bypass/revalidate the cache so "full is always safe" remains true. A content-sensitive version would close the underlying alias.

### MEDIUM — #724 resolves citations in the process CWD, not the repository supplied to `--repo`

**Files:** `dev/ledger.py:701-735`, `dev/ledger.py:1924-1929`

The commits come from `_git_subjects(args.repo, since)`, but `_resolved_cites()` runs bare `git cat-file --batch-check`. Thus `ledger.py sweep --repo /repo-B` launched from repo A resolves repo-B hashes against repo A and recreates the false positive #724 was meant to remove.

Concrete reproduction from this worktree using `/home/xertrov/src/c2c` as repo B:

```text
target_repo_resolves True
cwd_repo_resolves False
resolved_cites_result False
```

The cited 7-character c2c prefix and c2c's 8-character `%h` resolve to the same commit under `git -C /home/xertrov/src/c2c`, but the new predicate says uncited from this worktree. Pass `repo` through `sweep_text()`/`_resolved_cites()` and invoke `git -C <repo> cat-file ...`. Test with two independent repos and a deliberately different CWD.

### MEDIUM — #730 verifies a PID number, not the process identity gathered for that PID

**Files:** `dev/reaper.py:232-264`, `dev/reaper.py:344-367`, `dev/reaper.py:370-425`

The record retains elapsed time but not `/proc/<pid>/stat` starttime. `_wait_for_exit()` polls only `kill(pid, 0)` and state. If the signalled watch exits and the kernel reuses its PID within the 3-second window, the replacement's live state makes the original report `SIGNALLED` even though it exited. More seriously, the pre-existing gather-to-SIGTERM window at line 419 can signal the replacement process because identity is not revalidated immediately before the kill.

Capture starttime in each gathered record, re-read it immediately before SIGTERM, and pass it into `_wait_for_exit()`. A missing PID or changed starttime means the original is gone; a changed starttime before signalling must refuse rather than kill.

State audit: treating `Z` as gone is right for this tool — it cannot run and has released files/sockets. `PermissionError` as alive is conservative. `D` (uninterruptible sleep) and `T` (stopped/traced) are correctly treated as alive and become `SIGNALLED` at timeout. Linux's rare `X`/`x` dead states are not recognized, so they can produce a transient false `SIGNALLED`, but PID identity is the material gap.

### LOW — #641 claims byte-identical reconstruction, but implementation and test prove only mapping equality

**Files:** `watch.py:3946-3974 @ 4e83d224`, `test_watch.py:13170-13207`; contract at `file-formats.md:2181-2188`

`compute_delta()` iterates `set(prev) | set(nxt)`, so added keys enter `changed` in hash-dependent order; `apply_delta()` preserves that order. Across `PYTHONHASHSEED=1..4`, the same `alpha/beta/gamma/delta` target reconstructed in four different serialized orders. The born-red test uses `assertEqual(dict, dict)`, which ignores order. The browser also carries the base's old `generated` value rather than "re-stamping" it.

This is not a current UI correctness failure: all present `collect()` top-level keys are fixed across a running generation, nested mutations ship whole, and the integrity hash sorts keys. Either weaken "byte-identical" to semantic/canonical equality, or preserve target key order and test serialized bytes. Generated exclusion itself is consistent between Python delta and hash; the prose about the receiver re-stamping it is not true of the browser.

### LOW — #724's advertised fallback does not catch resolver startup or timeout failures

**Files:** `dev/ledger.py:701-735`

The docstring says an unavailable git answer falls back to substring behavior, and sweep is advisory, but `subprocess.run(... timeout=20)` is outside any exception handler. Injecting `subprocess.TimeoutExpired` produces an uncaught `TimeoutExpired`; an unavailable executable produces an uncaught `OSError`. A cold/promisor object store crossing 20 seconds therefore crashes the sweep rather than printing an advisory result.

Catch `OSError` and `subprocess.SubprocessError`, then return the documented substring predicate (and make the degraded mode visible if the advisory contract requires it). Ambiguous and foreign-repo hashes that reach `cat-file` are otherwise fail-safe: they do not suppress a finding. One rare exception remains from the legacy fast substring path: a foreign full SHA beginning with the local `%h` is accepted without resolution.

### LOW — #725's phrase regex also matches negated, historical, and meta-description titles

**Files:** `lint.py:1935`, `lint.py:2019-2035`

`\bblocked on\b` is a useful measured heuristic, but it is not the claimed class "a title claiming this task is blocked." Concrete empty-`blocked_on` false positives all match today:

```text
not blocked on #614 anymore
Explain why jobs are blocked on CI
Document the `blocked on` title lint
```

The first is especially perverse: the correct retitle after a ruling still warns that the field is empty. Either narrow obvious negation/meta forms or lower the claim in docs/tests from zero-false-positive grammar to an intentionally noisy phrase heuristic. Add at least negated and quoted/code-span cases.

## Areas checked without a serious finding

| Lane / concern | Result |
|---|---|
| #641 delta derivation | Nested values ship whole; add/remove and generated exclusion are internally correct. Two writes between polls reconstruct final state if the watched version advances. Findings above cover ordering, version aliasing, and the JS/server disagreement. |
| #641 restart and burn-step cache | A changed server generation reloads the page; an unknown `since` returns full. Cache keys include `burn_step`, and `cycleBurnStep()` clears the held version on the normal sequential path. |
| #730 `Z`, `PermissionError`, `D`, `T` | Semantics are appropriate as described above; the remaining problem is process identity/PID reuse. |
| #724 ambiguity / foreign objects / batching | Ambiguous or missing objects do not suppress findings. One batch process is reasonable; wrong repo selection and uncaught cold-cache timeout are the gaps. |
| #728 exception narrowing | `count_lanes()` catches only `OSError`; `ValueError`/`TypeError` reach `main()` and render the explicit `COUNT-BROKEN` line. The named `live_lane_count()` accessor removes the arity unpack from the caller. Checked clean. |
| #725 store/Markdown dispatch | Empty/whitespace store values and Markdown's structured human marker are handled as intended. The remaining concern is regex classification, not field dispatch. |
| #607 interpreter/subject wording | The new wording is accurate and preserves the explicit baseline exception. Checked clean. |

## Verification

- `python3 -m pytest test_watch.py test_reaper.py test_ledger.py -q` — **554 passed, 62 subtests passed**.
- `python3 -m pytest test_lint.py test_guard_preflight.py test_status_sync.py test_redproof.py -q` — **629 passed**.
- `git diff --check 1ab60a3c...HEAD` — clean.
- No browser guards were run; ports 35110 and 35113 were untouched.
- No source file was modified. This report is the only worktree content change.
