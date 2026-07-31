# Lane 744 report — process identity for reaper verification

## Verdict

PASS. The reaper now gathers `/proc/<pid>/stat` field 22, requires that
starttime to match immediately before SIGTERM, and tracks the same starttime
through the bounded exit wait. A pre-signal mismatch refuses without sending a
signal; a missing pid or post-signal mismatch means the gathered process is
gone. The audited state meanings were not changed.

Rebased cleanly from base `b73e4a349c08` onto local `master`
`ecd3a09f7010`. Post-rebase implementation commits:

- `6290817b` — `fix(#744): verify reaper process identity`
- `dfe38350` — `test(#744): discriminate pid reuse refusal`

No merge or push was performed.

## Change

- `dev/reaper.py`: added one safe `_process_stat()` reader that parses from the
  last `)` and returns state plus starttime from the same stat read. Gathered
  records retain starttime. `do_kill()` distinguishes missing, unreadable, and
  changed identities before SIGTERM; `_wait_for_exit()` treats a changed
  starttime after SIGTERM as the original process gone.
- `test_reaper.py`: grew from 22 to 31 tests. New assertions bind starttime
  gathering, the exact changed-identity refusal, missing and unreadable stat as
  different facts, post-signal reuse, absent gathered identity, and the
  existing self/init guards. Existing tests continue to bind
  `DREAMWORK_REAP_NEVER_KILL` and `is_deployed` before any signal.

The existing `Z`/`PermissionError`/`D`/`T` meanings remain intact: only the
identity condition was added around them.

## Red-proof

### Direction 1 — real defect reintroduced

Used `python3 dev/redproof.py begin dev/reaper.py`, changed the pre-SIGTERM
mismatch condition to `if False and ...`, confirmed that injected source was
present, and ran only the discriminating test. It failed with:

> `AssertionError: a reused pid must be refused before SIGTERM`
>
> `assert [(424246, 15), (424246, 0)] == []`

Thus the check fails because the reused pid was signalled, not merely because a
count changed. `python3 dev/redproof.py restore dev/reaper.py` restored and
byte-verified the fixed file. Final hand-off gate:

> `check: clean — 1 injection(s) registered, all restored and absent from the working tree and from this branch's commits`

It examined all three commits since rebased master and found zero injected blobs.

### Direction 2 — constructed false-green that remains

A fully fabricated record used gathered starttime `111`. The preflight read
also returned `111`, then the fake replaced the process before the fake
`os.kill`; the recorder showed SIGTERM hitting the replacement, and the wait
read starttime `222`. The current tool returned the original record as REAPED:

> `DIRECTION 2 FALSE-GREEN: preflight starttime matched 111; replacement arrived before SIGTERM; fake SIGTERM hit replacement; post-signal starttime 222 made original read gone/REAPED.`

No real signal was sent. This is the unavoidable userspace TOCTOU between the
last `/proc` read and `kill(pid, SIGTERM)`: the fix narrows the window but does
not eliminate it. Linux pidfds could close more of this class, but widening to
that mechanism is outside this small task. A record collected in a different
PID namespace is another identity-context hazard; starttime alone does not
encode namespace identity.

## Safety and verification

- `python3 -m pytest test_reaper.py`:
  `collected 31 items` / `31 passed in 3.77s`.
- `python3 lint.py`: `clean (6 warning(s))`; all six are pre-existing,
  explicitly rendered worktree/ledger/status/lesson warnings, and there are no
  ERRORs.
- `python3 dev/redproof.py check`: clean after the rebase, zero commits holding
  the injection.
- `git diff --check master...HEAD`: clean.
- Live sanity check used only
  `DREAMWORK_REAP_NEVER_KILL=1 python3 dev/reaper.py` in default dry-run mode.
  It said `dry-run (kills nothing)`, found 0 dead-lane targets, and sent no
  signals. Ports `:35110` and `:35113` were only reported; neither was touched.
- Protection assertions that would fail on regression:
  `test_init_and_self_pids_are_protected_before_identity_read` requires no
  `/proc` read or `os.kill` for pid <= 1 and self; the existing never-kill test
  requires no signal under `DREAMWORK_REAP_NEVER_KILL`; the deployed-dashboard
  test requires no signal for either sweep or explicit `--pid` targeting.

## Relied-on ledger lines

- #744: “Capture starttime (field 22 of `/proc/<pid>/stat`) in each gathered
  record; re-read it immediately before SIGTERM; pass it into
  `_wait_for_exit()`.”
- #730: “DO NOT auto-escalate to SIGKILL.” This remains unchanged.
- #136: “THREE zero-states, not one”; applied here so different-process,
  already-gone, and unreadable-stat do not render as one fact.
- #288: “no host, service, sandbox, privilege or deployment change
  authorized”; all live-table work stayed dry-run and all identity-reuse
  signals were recorders over fabricated pids.
- #729: the landed note says stat parsing “cuts between the FIRST and LAST
  paren for comm because comm can contain spaces and parens”; the reaper's
  existing last-`)` parser was reused rather than whitespace-splitting the raw
  line.

## Out of scope

The preflight-to-SIGTERM window above remains real. Closing it further needs a
separate pidfd design and portability decision; it was not smuggled into this
bounded change.

## DOGFOOD REPORT

Friction found: `python3 dev/lessons_index.py --act red-proof` returned 42
lessons and 533 lines, enough for the tool output to truncate. The required
snapshot/restore lesson was visible, so it did not block this lane, but an
act-index intended to put the relevant handful in reach is now itself too
large to reliably read as one result. The index would benefit from a bounded
high-relevance view while retaining an explicit count/list of omitted matches.

Otherwise the lane boilerplate was accurate: the worktree-local red-proof
tool created a lane-private snapshot, restored by copy, verified the bytes, and
the final `check` correctly re-evaluated the rewritten post-rebase commits.
