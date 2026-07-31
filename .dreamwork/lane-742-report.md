# Lane 742 report — no-`since` full truth

## Verdict

Land the minimum fix now and file the content-sensitive version as separate
work. No-`since` `/data.json` requests now rebuild from `collect()` instead of
trusting the mtime-keyed cache, so the recovery path added by #741 converges
after an aliased version. The ordinary `since` cache remains deliberately
mtime-keyed; this increment does not claim to close that underlying alias.

No `file-formats.md` change is needed: this restores its existing “full is
always safe” contract rather than changing the format or wire behaviour.

## Change

- `watch._data_json_cached(target, burn_step, since=None)` rebuilds whenever
  `since` is absent. The route now parses `since` before consulting the cache
  and passes it through.
- Same-mtime mutation coverage asserts the discriminating fact: the fresh
  document contains `SAME-MTIME-MUTATION`, and the served no-`since` document
  must contain it too.
- Each `burn_step` remains a separate cache key, but a no-`since` request for
  either tested key rebuilds that key. The bypass is not accidentally limited
  to the default step.
- Two ordinary writes between polls are confirmed safe: the next lookup
  compares the original cached version directly with the final version and
  the rebuilt document contains both writes.

Rebased cleanly onto local `master` `1c055ab25eac3bc94e6cd3cf3207fc1b2eb59417`
before this report. No conflicts occurred. Post-rebase implementation head:
`b40ed662829719f86bbb31a8a4b45d81ee3091f2`.

## Options weighed (IGC)

Context: #741 is landed and its rejection/self-heal path refetches without
`since`; the server change must be a small reliable increment, while the
existing phase-1 budget was roughly 60–90 server lines.

| Idea | All | G1 | G2 | G3 |
|---|:---:|:---:|:---:|:---:|
| Minimum bypass now; file deeper work | ✔ | ✔ | ✔ | ✔ |
| Content-sensitive version now | ✘ | ✔ | ✘ | ✔ |
| Partial content-sensitive version | ✘ | ✘ | ✔ | ✘ |

- G1: #741 recovery converges now under the reproduced alias.
- G2: this increment has bounded, measurable cost and fits the lane budget.
- G3: do not falsely claim or partially close the underlying alias.

The decisive error for the deeper fix *in this increment* is cost and
unmeasured performance. A truthful content-sensitive version must hash every
input capable of changing `collect()` — including the `.dreamwork` tree,
listing changes, git state, and live SQLite DB/WAL inputs — on the polling hot
path, or build and hash the whole collected document. Either approach largely
spends the work the cache avoids, needs stable concurrent-file semantics, and
changes the version contract. An incremental/inotify design is a larger
cross-platform state machine and still needs a story for timestamp-preserving
external restores. A few lines that hash only the obvious Markdown files would
be the rejected half-fix: it would make a broader correctness claim without
covering all `collect()` inputs. File the deeper design with performance
measurements rather than landing that shape here.

## Red-proof

### Direction 1 — the real defect goes red

The born-red test first failed on the unfixed tree with the discriminating
message:

> `AssertionError: 'SAME-MTIME-MUTATION' not found ... no-since served a stale cached document: the fresh build contains SAME-MTIME-MUTATION but the response does not`

After the fix, `dev/redproof.py` snapshotted `watch.py`; I removed only the
`since is None` rebuild arm and reran that exact test. It failed on the same
message. Restore was via `python3 dev/redproof.py restore watch.py`, never git
checkout. Final required check:

> `check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits:`
>
> `watch.py (sha 7df4b8824243, hint: 'if entry is None or entry[0] != version:')`

That assertion catches stale *served content*, not merely reuse of a cache
object.

### Direction 2 — try to make the check pass while truth is stale

The underlying false-green remains constructible for a request that still
sends the aliased version. Measured after the fix:

> `version_equal_at_lookup True`
>
> `held_has_mutation False`
>
> `since_response_unchanged True`
>
> `fresh_has_mutation True`
>
> `no_since_has_mutation True`

Thus a client that never enters recovery can still hold stale state; this is
the exact residual the deeper content-sensitive version must close. The claim
here is only that #741's no-`since` recovery converges.

The proposed burn-step false-green did not survive: the named test prepopulates
both `(target, None)` and `(target, BURN_STEPS[0])`, performs the same-mtime
mutation, then proves a no-`since` lookup for each key serves the marker. A
file outside `watched_mtime` cannot defeat this no-`since` check: the code calls
`collect()` unconditionally, so if `collect()` observes that file the response
does too; if it does not, there is no fresh-versus-served content difference to
hide. Such a file can still poison a `since` request, which is already exposed
by the residual construction above.

## Issue evidence read

- #742: “A no-`since` request is supposed to mean ‘give me the full truth’.”
- #641: “`Full is always the safe answer` held: mismatch, unknown since, or
  new server generation all fall back to the whole document.”
- #741: “Every failure path clears `lastDataV` and refetches WITHOUT `since`.”
  Its landing records base capture/validation, response sequencing, and that
  no-`since` recovery path; this lane assumes those landed semantics.

## Verification

- Before: #741 recorded `484 tests`.
- Targeted after rebase: `10 passed in 2.96s`.
- Full after rebase: `487 passed in 39.27s` using two pytest workers.
- `python3 lint.py`: `clean (6 warning(s))`, with **no ERRORs**. The six are
  the existing worktree/ledger/status/questions/lessons warnings printed in
  full by the command; notably the ledger checks explicitly examined nothing
  because the gitignored SQLite store does not travel to the lane.
- No browser guards were run, per the task instruction. No server was started
  and no port was bound.

## Out of scope / follow-up

File a focused deeper-version task. Its acceptance bar should inventory every
input to `collect()`, define content-version semantics under concurrent SQLite
and file writes, measure the polling cost on a real target, and prove that a
normal `since` client cannot receive `unchanged` while a fresh build differs.

## DOGFOOD REPORT

No Dreamwork tooling or brief friction found. `dev/redproof.py` selected a
lane-private snapshot, restored with byte verification, and its post-rebase
history scan clearly proved that no committed injection survived. The absolute
ledger invocation and explicit test-count/report obligations were reachable
and unambiguous.
