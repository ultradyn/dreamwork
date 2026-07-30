# Brief — #124: refresh parallel-architecture.md to the lived fleet reality

Task: **#124** (P2 — "Break up watch.py; norms for cheap parallel work;
seams as batches demand them"). Its plan `.dreamwork/docs/plans/parallel-
architecture.md` predates the entire multi-lane era. Your job: audit the
plan against current practice and rewrite it so it describes the fleet as it
actually runs + the norms that were learned the expensive way.

## Lane-owns

- `.dreamwork/docs/plans/parallel-architecture.md` (in-place refresh)
- `.dreamwork/docs/findings/124-refresh-notes.md` (optional, if you need a
  scratch evidence pad)

Everything else READ-ONLY. No servers, no ports, no code edits.

## What the plan must catch up to (verify each, cite file:line)

- **Harness-clone lanes** (`spawn_subagent` isolation=worktree) are
  independent `.git` clones — invisible to `git worktree list` and to
  `dev/lane_guard.py`'s `wt/*` registry (the #423 audit finding,
  `.dreamwork/docs/findings/423-dead-runner-audit.md`). Two lanes have
  committed directly on master and been accepted after verification.
- **`git commit --only <paths>`** is the concurrency rule (CLAUDE.md) —
  `git add` does not protect you; the `12f47e3` incident.
- **The #535 exit-dirtiness habit** (SKILL.md): porcelain + log check at
  lane completion; the three outcomes.
- **The #537 `dispatch` field** on dreamers entries (file-formats.md):
  unobservable dispatch forms carried past the liveness probe.
- **The #465 open defect** (P1): a lane can edit the MAIN CHECKOUT and
  nothing notices until a merge fails — one half awaits his consent.
- **Lane-owns declarations + coord-inbox DONE reports + handoffs.md** as
  the coordination protocol; the merge-gate with independent red as the
  quality bar (CLAUDE.md verification section).
- **watch.py is still one 14k-line file** and the single-writer bottleneck
  — the fleet routes around it by ownership (one watch.py lane at a time,
  everything else READ-ONLY). The plan's "seams as batches demand them"
  prediction: did it happen? (The #505 reconciler extracted a vendored
  dependency; bin/ud-dw-chat imports watch rather than re-implementing.)

## Shape

Keep whatever in the plan is still true (verify before keeping). Name what
is SUPERSEDED and by what (with shas where known). The rewrite should let a
fresh coordinator run a 4-lane fleet from the doc alone: dispatch shape,
ownership grammar, merge-gate, the known containment gaps and their status.
End with the re-scoped remainder of #124: is "break up watch.py" still the
right goal, or has the ownership grammar made it unnecessary except for
specific seams (name them)? This is a recommendation to HIM, not a ruling.

## Reporting

Append to `~/.cache/agent-comms/ud-dreamwork/coord-inbox.md`:
`[lane-124plan] DONE <sha> — <one line>` plus: superseded sections named,
the remainder recommendation in one line. Use `dev/relay.py` if present;
never `attn`. Then append one line to `.dreamwork/handoffs.md` **inside
your worktree** and commit it there:
`- **#124** · landed \`<sha>\` · <YYYY-MM-DD HH:MM> · by <you> — <what>`.
Do not claim a model you were not dispatched as. NEVER read image files
(your model cannot process them; it will crash your turn).
