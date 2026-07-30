# Brief — #260: post-compaction submission reconciliation, cursor-based

Task: **#260** (P1, reliability; incident confirmed by human 15:47 — a
coordinator guessed a cutoff after a cancelled compaction and falsely
concluded no missed messages before scanning the full witness).

## Lane-owns

- `dev/reconcile_submissions.py` (new tool; name may vary — justify the choice)
- `test_reconcile_submissions.py` (new)
- `file-formats.md`, `lint.py`, `test_lint.py` (only if the tool introduces a
  parsed file shape or warrants a proportionate check)

watch.py is **READ-ONLY** (lane-505p2 owns it). Anything you believe must
change in watch.py is a FLAG in your report, not an edit.

## Act 0 — evaluate against what landed (this comes first)

The filing predates the user-event journal drain. Since it: every write
route commits a receipt to the journal BEFORE dispatch (E3 cutover), and
`dev/journal_consume.py pending | consume --through <ord>` gives a durable
coordinator cursor with an applied-proof (#526) and a bounded advance
(#531). Determine and state, with file:line citations: **does the journal
cursor already close the #260 incident?** The incident was *submissions*
(submissions.log, #199 — verbatim and complete, watch.py:14481) missed by a
post-compaction coordinator. If every submission that matters is also a
journaled receipt, the drain may already be the cursor-based reconciliation
asked for — in which case the gap is only what the drain does NOT cover.
Enumerate precisely which submission kinds (command/comment/answer/ask/tint
— the filing names them separately) are journaled and which are not.

## Acts 1+ — close the gap that Act 0 actually found

- If some kinds are unjournaled: build the reconciliation over
  `submissions.log` for those — a durable/best-effort processed cursor
  (file-formats entry in the same commit if a new file shape), enumeration
  of every later record by endpoint/kind, mapped to the task/question/
  answer/settings folding it represents, exact text preserved.
- If ALL kinds are journaled: the gap is operational, not architectural —
  the smallest true fix may be a `reconcile` verb that cross-checks the
  journal cursor against submissions.log (a witness audit: every
  submissions.log record maps to a receipt id or is named as unjournaled),
  so a post-compaction coordinator can PROVE "no missed messages" instead
  of guessing a cutoff. Build that.
- Either way: red-first tests including an incident fixture (a submissions
  log + cursor positioned mid-stream; recovery must enumerate exactly the
  later records, none earlier, none missed — derive the expected set at
  runtime from the fixture, never a literal tuned to it).
- Red-proof each binding check by sabotaging the production line it binds
  (name the line), watch it fail, `cp`-restore byte-identical. NEVER
  `git checkout`. A green red-run is a finding, not a relief — report it.

## Constraints

- Never `just test` / the guard suite; your owned pytest files only.
- Do not bind ports. No `attn`, no `pkill -f`.
- Commits: `git commit --only <paths>` inside your worktree.

## Reporting

Append to `~/.cache/agent-comms/ud-dreamwork/coord-inbox.md`:
`[lane-260recon] DONE <shas> — <one line>` plus lines for: the Act 0 verdict
(journaled kinds enumerated, the gap named), every red-proof (production
line → failing test), and any watch.py flags. Use `dev/relay.py` if present;
never `attn`. Then append one line to `.dreamwork/handoffs.md` **inside your
worktree** and commit it there:
`- **#260** · landed \`<sha>\` · <YYYY-MM-DD HH:MM> · by <you> — <what>`.
Do not claim a model you were not dispatched as.
