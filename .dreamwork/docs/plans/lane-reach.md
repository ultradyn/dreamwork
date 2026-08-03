# Lane reach — augment a running lane without interrupting it

> **Status:** design only for `#998`; no channel is wired by this document.
> The first build increment is a runner-independent, lane-private correction
> store plus frame checkpoints. It does not kill, pause, resume, or re-dispatch
> a runner. The present end-to-end guarantee is deliberately named
> **best-effort until acknowledged**.

## Verdict

Reuse `#652`'s per-launch `lane_scratch` identity and add a small `reach/`
protocol beside the lane's existing scratch data. A coordinator queues one
immutable factual correction; the standard lane frame requires the lane to
check at four phase boundaries; the checker presents every unacknowledged
correction again; and the lane writes an explicit acknowledgement only after
it has assessed the correction. The coordinator may distinguish `QUEUED`,
`ACKNOWLEDGED`, and `RESOLVED`, but may never infer one from another.

This is cooperative augmentation, not a control channel. A lane inside a long
tool call cannot look until the call returns, and a fallible lane can skip a
prompted checkpoint. The mechanism therefore does not claim guaranteed
attention. Its useful promise is narrower: a small correction has a durable,
lane-specific place to wait, a repeated reason to be read before more work is
committed, and an acknowledgement whose absence remains visible.

## Premises and boundary

- **VERIFIED — dispatch has already consumed the only runner prompt.**
  `dev/dispatch_lane.py::_launch_detached` execs `[*runner, prompt]` in a new
  session and the dispatcher exits. There is no loop-owned stdin or session
  object left to write later.
- **VERIFIED again on 2026-08-03 — no current runner control.** `ccc --version`
  reports `0.4.2`; `ccc --help` exposes invocation controls, output modes,
  timeout, aliases and raw runner arguments, but no live message, attach, or
  resume operation.
  A design resting on such an operation would invent its decisive seam.
- **VERIFIED — `#652` solved the path and launch-identity half.** Every dispatch
  creates 128 random bits in `DREAMWORK_LANE_ID`; `lane_scratch_dir` keys on
  repo + worktree + that launch identity + role. Two launches in one worktree
  therefore do not share storage.
- **VERIFIED — the coordinator cannot rediscover that exact path today.** The
  launch token lives only in the child environment, while `.dreamwork/lane.lock`
  records pid/task/lane/brief/process identity but not `DREAMWORK_LANE_ID`.
  `lane_identity_dirs` can enumerate old identities after the fact; choosing
  one of several is not an addressing protocol. The increment must persist the
  launch token in the live lock and extend the existing path helper to accept
  that explicit identity. It must not recreate `lane_scratch`'s path formula.
- **BOUNDARY from `#450`.** Dreamwork owns neither the harness's model call nor
  its tool-execution loop. The process/tool-call containment note is primary:
  cooperation is the available seam on trusted nodes. Harness write
  containment is adjacent evidence that cwd and prose are not mechanical
  barriers; it does not turn a correction into file-write interception.

The message type is intentionally narrow: a factual correction or an added
requirement that remains inside the dispatched task and its declared
`Lane-owns:` surface. It is not a replacement brief, a scope expansion, a kill
request, or permission to override safety evidence. If ownership or the task's
goal must expand, use a new round. The helper cannot prove semantics from prose,
so both coordinator and lane carry this rule; the lane reports a violating
message as `BLOCKED` rather than obeying it.

## IGC choice

**Context.** One detached `ccc` runner has consumed its prompt; the loop and
runner share a trusted UID; corrections are usually one path or citation; a
lane may be deep in a tool call; the gate separately excludes writes to the
shared brief corpus; and re-dispatching a corrected round already works.

**Binary goals.** G1: a correction can be presented before report without
stopping the lane, provided it reaches a required checkpoint. G2: queued,
read, acknowledged, absent, empty, and broken states are distinguishable. G3:
two launches in one worktree cannot consume each other's corrections and the
lane's branch stays clean. G4: the idea works with current `ccc` and assumes no
unmeasured harness capability. G5: it does not write the shared brief corpus
and may therefore coexist with a live gate. G6: an early small correction can
avoid one corrected re-dispatch cycle rather than waiting only for handoff.

| Idea | All | G1 | G2 | G3 | G4 | G5 | G6 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| I0 — keep kill/re-dispatch as the only path | ✘ | ✘ | ✔ | ✔ | ✔ | ✔ | ✘ |
| I1 — `<worktree>/.dreamwork/lane-inbox.md` + checkpoints | ✘ | ✔ | ✔ | ✘ | ✔ | ✔ | ✔ |
| **I2 — `lane_scratch`-adjacent store + checkpoints** | **✔** | **✔** | **✔** | **✔** | **✔** | **✔** | **✔** |
| I3 — send a live message to the runner process | ✘ | ✔ | ✔ | ✔ | ✘ | ✔ | ✔ |
| I4 — deliver only at rebase-before-report | ✘ | ✔ | ✔ | ✔ | ✔ | ✔ | ✘ |

**I0 decisive errors.** It interrupts the lane and cannot save the additional
round. It remains the honest null/fallback, not the chosen reach mechanism.

**I1 decisive error.** A reused worktree needs a new generation protocol or a
later launch can read stale messages. The file also dirties or requires a new
ignore exception inside the lane's workspace. Both duplicate boundaries
`lane_scratch` already solved outside the repo, so G3 fails.

**I3 decisive error.** `ccc 0.4.2 --help` advertises no attach/message/resume
control, and dispatch retains no writable stream. A richer interface may be
reconsidered only after a specific runner capability is measured. Today it
fails G4.

**I4 decisive error.** The existing rebase-before-report point is a useful
last checkpoint, but it arrives after implementation and verification. It can
improve the final report or stop a false handoff; it cannot save the current
work cycle, so G6 fails.

**I2 survivor.** It combines the already-correct address boundary with the
missing attention and receipt protocol. Storage alone is not the answer: the
frame checkpoints and explicit acknowledgement below are part of I2, not a
later enhancement.

## Protocol and state truth

The proposed helper is `dev/lane_reach.py`; it imports `dev/lane_scratch.py`
for repo/worktree/identity derivation. Do not add a second path algorithm.
Dispatch creates the channel before exec and records the same `launch_id` in
the live lane lock. The exact root is the author lane's scratch directory plus
`reach/` and contains:

```text
reach/
  channel.json
  messages/000001.json
  messages/000002.json
  acknowledgements/000001.json
```

`channel.json` is an atomically-created schema marker carrying version,
launch id, task, lane, worktree and creation time. Each message is immutable,
create-exclusive, checksum-bearing JSON with sequence, message id, timestamp,
kind=`correction`, body, and the original task/scope identifiers. Each
acknowledgement is immutable and names exactly one message id, the time seen,
the lane's disposition, and a short reason. Temporary files, rename, directory
fsync, and a per-channel writer lock prevent a half-write from looking empty.

The observable states are deliberately separate:

| observation | meaning | coordinator may say |
|---|---|---|
| no channel marker for a live lock | initialization failed or unsupported | `BROKEN: channel absent` |
| valid marker, zero messages | healthy channel with no correction | `EMPTY: no correction queued` |
| malformed/unreadable marker, sequence gap, checksum mismatch | channel cannot be trusted | `BROKEN`, with the exact fault |
| valid message, no acknowledgement | bytes durably stored; attention unknown | `QUEUED`, never “delivered” |
| explicit acknowledgement | lane says it read and assessed the body | `ACKNOWLEDGED: <disposition>` |
| acknowledgement plus later final report/commit evidence | lane completed its chosen response | `RESOLVED` |

This is `#136` applied directly: absent, empty, and broken are three results.
It is also the `#651` correction: no status line names a failure mode its
measurement cannot detect.

### Delivery guarantee

The **end-to-end guarantee is best-effort until explicit acknowledgement**.
The coordinator may assume only that `QUEUED` means durable bytes addressed to
the current live launch. It may assume the lane read the correction only after
the lane writes an acknowledgement, and may assume the work incorporated it
only from the disposition plus subsequent evidence.

Within that boundary, presentation is **at-least-once**: `check` prints every
unacknowledged message on every checkpoint. A crash after acting but before
acknowledging causes a repeat, so corrections must be idempotent factual
statements rather than imperative one-shot actions. Acknowledgement makes later
checks omit the message. Exactly-once processing is neither required nor
claimed.

An acknowledgement is explicit, not written automatically by `check`.
`check` proving it opened bytes is not proof the lane assessed them. The lane
uses `ack <id> --disposition applied|premise-invalid|blocked|noted --reason ...`
after deciding. Even this remains a cooperative report from a trusted-but-
fallible lane; the channel does not claim access to model cognition.

## Attention: why the lane looks

Every dispatched frame names the same command and four mandatory checkpoints:

1. after orientation/premise reads and **before the first edit**;
2. before each commit (and the existing commit path should run the same check
   as a backstop, refusing while an unacknowledged correction is pending);
3. after any rebase or merge and before re-running/citing evidence;
4. immediately before the final inbox report, before capturing the reported
   SHA.

The frame says what a pending correction requires: read it, assess it against
current evidence and scope, acknowledge a disposition, then continue. The
pre-commit backstop supplies one mechanical reason before work becomes durable;
the rebase/report checkpoint reuses an existing mandatory transition for the
last delivery slot. The first checkpoint is what catches the common path or
citation correction early enough to save work.

This does not make a lane interruptible. No signal is sent; no tool call is
cancelled; no runner is paused. A correction waits until the next checkpoint.
If a lane never reaches one, `QUEUED` remains visible and the coordinator uses
the null option. That ceiling follows from `#450`; hiding it would turn
cooperative attention into a fictional harness feature.

## What the lane does after reading

The correction is evidence, not an instruction to abandon work. The lane owns
the decision:

- If the corrected fact leaves the task and ownership intact, amend the work
  and evidence, acknowledge `applied`, and continue.
- If it refutes the premise or makes completed work unnecessary, stop new work,
  acknowledge `premise-invalid`, and report the corrected premise and what was
  already done. `#1102` demonstrates that this can be the cheapest correct
  outcome.
- If it conflicts with observed evidence, asks for new owned files/goals, or
  would weaken a safety rule, acknowledge `blocked` with the conflict and
  continue only with work whose premise still holds.
- If it changes only final context and needs no code change, acknowledge
  `noted` and carry it into the report.

No disposition authorizes a destructive action. “Stop and report” is never a
remote control operation; it is the lane's conclusion from the corrected
premise.

## Gate and dispatch-ban interaction

A reach correction is **not a dispatch** for `gate-worktree.md`'s exclusion.
It creates no runner, brief, receipt, task, branch, worktree, or shared-corpus
write. The channel lives under `~/.cache/.../lane-scratch`, so queueing and
acknowledging may occur while a gate holds the corpus-write exclusion.

That answer is narrow. Reaching a lane does not relax the ban on a new dispatch
and cannot mutate the persisted brief to disguise one. A message that expands
the task or `Lane-owns:` is `blocked` and waits for a corrected round after the
gate. If a later implementation puts reach records in the brief corpus, this
ruling becomes false and must be revisited before that storage change lands.

## Cost against the null option

The null option is sound: stop/finish the old lane and dispatch a corrected
round. It costs one additional lane cycle and preserves a clean authority
boundary. Reach saves **between zero and one cycle per correction**:

- near the first checkpoint, a one-path or one-citation correction can save
  almost the whole corrected round;
- during a long tool call or at the final checkpoint, it saves little or no
  elapsed work, though it can still prevent a false handoff;
- if the lane skips checkpoints or the correction changes scope, it saves
  zero and the null option remains necessary.

Of the five motivating instances, one lane (`#1102`) found the dead premise
itself and needed no channel to reach the right outcome. Four were small factual
corrections of the shape this increment can carry. That supports building a
cheap cooperative path; it does not establish a throughput rate or guarantee
four saved cycles retrospectively.

## Dispatchable increments

### Increment 1 — address, queue, check, acknowledge

**Likely files:** `dev/lane_scratch.py`, `dev/lane_reach.py`,
`dev/dispatch_lane.py`, the lane-lock contract in `file-formats.md`, the
standard dispatch frame in `SKILL.md`, focused tests, and the existing commit
hook path for the pending-correction backstop.

Persist the launch id in the lock, add an explicit-identity entry point to
`lane_scratch` rather than copying its derivation, initialize the marker before
exec, and implement `queue`, `status`, `check`, and `ack`. Tests must separate
absent/empty/broken; prove two launches in one worktree do not cross-read;
prove a queued message repeats until explicit ack; prove an ack for a different
launch/id refuses; prove a malformed or gapped channel cannot print clean; and
prove no command writes inside the repo or brief corpus.

The born-red defect is a checker that silently treats an absent channel as
“nothing pending.” The tracked expectation must require the exact
`BROKEN: channel absent` result before implementation changes, then the
positive control creates a valid empty marker and requires `EMPTY`.

### Increment 2 — visibility, only after measured use

Expose `QUEUED` versus `ACKNOWLEDGED` in the coordinator's existing lane view
only if live use shows the CLI status is too easy to miss. Do not add a push
channel, timer process, or general chat protocol by default. Measure correction
age, time-to-ack, checkpoint reached, disposition, and whether a re-dispatch
was avoided; those observations decide whether a richer harness integration is
worth investigating.

## Reopen conditions

Re-run the IGC if `ccc` gains a measured live attach/message API, if lanes move
to an untrusted-node threat model, if the gate's corpus authority changes, or
if measured use shows checkpoints are routinely skipped. Until then, the
honest design is durable cooperative reach with visible non-acknowledgement,
not a control channel wearing an inbox's name.
