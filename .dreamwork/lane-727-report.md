# Lane report: tasks #727 and #735

## Verdict

PASS, with one merge instruction: squash this branch when merging because the
red-proof history gate correctly found the pre-fix `.gitignore` state in the
first task commit.

## #727 — live-lane label

Changed the tick's OS-observed fleet clause from the stale aggregate
`N ccc-live` to `N ccc + M agent-tool live`. The split is available at the
render point: `status_sync.live_lanes()` returns the surviving entries, and
each survivor retains `dispatch`; an absent dispatch is the documented legacy
ccc default. The implementation counts unique task ids per dispatch, preserving
the prior set-count semantics, and fails closed if an unknown dispatch appears
or one task claims both paths.

Decision, compact IGC. Context: choose the label from data already available in
`tick_line.py`, without changing `status_sync.py`.

| Idea | All | Accurate now | Distinguishes paths | In scope |
|---|:---:|:---:|:---:|:---:|
| `N lanes-live` | ✘ | ✔ | ✘ | ✔ |
| `N ccc + M agent-tool live` | ✔ | ✔ | ✔ | ✔ |

The neutral label is truthful but discards a distinction already present in the
survivors. The split is the only survivor because it says both what is live and
which observable dispatch path supplied each part.

Repository-wide literal search found no parser for `ccc-live`. Remaining
occurrences are the negative assertion in `test_tick_line.py` plus stale prose
in `SKILL.md`, the tick-line migration, `lint.py`, and `test_lint.py`; all are
outside this lane's allowed files.

Red-proof:

- Direction 1: injected `agent_live = 0`. The discriminating test failed with
  `assert "2 ccc + 1 agent-tool live" in out`; output instead contained
  `FLEET UNRESOLVED (LivenessUnknown: live lane has unknown dispatch)`.
- Direction 2: the first mixed-path test still passed if two live entries for
  the same task inflated a dispatch count, despite the old implementation
  counting unique task ids. Added
  `test_duplicate_task_does_not_inflate_a_dispatch_count` and changed both
  path counts to sets. Unknown future dispatches and cross-path task overlap
  now fail closed rather than silently mislabel.

Relied-on ledger text, read before implementation:

- #727: “So the tick line's `N ccc-live` figure now counts Agent-tool lanes
  too.”
- #675: “discover_lanes now returns agent_tool, deduped by lane name ...”
- #718: “The answer to ‘why are there three counters’ is THERE ARENT:
  recorded and runners both read the same hand-maintained
  status.json[\"lanes\"] ...”

Commits after the final rebase:

- `61d4536e052a9c4cd4b982ae9675d97fae72bf5f` — initial split and tests
- `b0a4ec0628ea8e6bae4b991b8dfc326d74546a50` — preserve unique-task counting

## #735 — pending-read ignore

Added `.dreamwork/user-events.sqlite3.pending-read` beside its SQLite siblings
in `.gitignore`. `git check-ignore -v` resolves it to the new rule.

Red-proof:

- Direction 1: removed the rule under `dev/redproof.py`; the check printed
  `EXPECTED RED: .dreamwork/user-events.sqlite3.pending-read is NOT IGNORED`.
  Restore verified the working copy byte-for-byte.
- Direction 2: the supported `--journal .dreamwork/custom.sqlite3` override
  derives `.dreamwork/custom.sqlite3.pending-read`; that path remains
  unignored while the default-path check passes. This is a real open
  false-green for custom in-repo journals, but broadening the requested exact
  one-line rule could hide intentionally tracked SQLite files, so I left it as
  an out-of-scope finding.

The requested construction inventory found no second persistent semantic
sidecar in `dev/*.py` or top-level `*.py`. It did find four unignored atomic
staging families that can remain after a crash:

- `.dreamwork/status.json.tmp` (`client_env.py`, `status_sync.py`)
- `.dreamwork/tasks.md.tmp` (legacy Markdown writes in `dev/ledger.py`)
- `.dreamwork/question-sigs.json.tmp` (`watch.py`)
- `.dreamwork/review/*.html.tmp` (`review_artifact.py`)

Other suffix constructions resolve outside the tracked tree: q-snap and
dreamhub use cache storage, deploy staging uses the deployment destination, and
the lane-guard `.prev` file lives under `.git/hooks`.

Relied-on ledger text:

- #735: “Its three siblings are gitignored and it is not.”

Commit after the final rebase:

- `6304477241f7756c3fa14c4105c47350b88b91e9` — exact pending-read ignore

## Verification and rebase

- `python3 -m pytest -q test_tick_line.py`: **46 passed in 0.88s** after the
  final rebase.
- `python3 lint.py`: **clean (6 warnings)**, with no ERRORs. The warnings are
  the expected worktree/store and existing questions/lessons warnings.
- `git diff --check`: clean.
- Rebases: first onto `ba2d3e10f0f7`, then onto `1d095ad3da65`; both completed
  without conflicts. The latter was local `master` at final verification.
- `dev/redproof.py check`: working tree restored, but REFUSED because the
  branch history contains the injected `.gitignore` bytes in the first task
  commit (the normal pre-#735 state). Its prescribed resolution is to squash
  this branch at merge.

## Dogfood report

The brief's targeted-test example, `just pytest -q <files>`, is not reachable
with this repository's current `justfile`: `just pytest -q test_tick_line.py`
treats `-q` as another recipe and errors with `Justfile does not contain recipe
'-q'`. I used the underlying targeted command
`python3 -m pytest -q test_tick_line.py`. The rest of the brief was precise,
especially the absolute ledger invocation and rebase-before-report ordering.
